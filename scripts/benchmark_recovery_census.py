"""Complete fixed-catalogue native recovery census, with every trial retained."""
import argparse
import contextlib
import io
import itertools
import json
import logging
import os
from pathlib import Path
import random
import shlex
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

import yaml
from threadpoolctl import threadpool_limits
from recoverml.core import canonical,digest,write_store
from recoverml.capability_retention import contract,retained_bytes,restricted
from recoverml.component_retention import optimize
from recoverml.witness import certificate
from recoverml.broad_workflows import capture,capabilities,DATASETS,RECIPES
from native_frontier_worker import reset_selected_cache
from broad_recovery_worker import recover

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'scripts/broad_recovery_worker.py'


def dump(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def catalogue(config,dataset,recipe):
    return [f'{dataset}/{recipe}/v{v}/{loss}/{request}/{interface}'
            for v,loss,request,interface in itertools.product(config['versions'],config['losses'],
                                                              config['requests'],config['interfaces'])]


def run(output,config_path,dataset,recipe,smoke=False):
    output.mkdir(parents=True,exist_ok=False)
    config=json.loads(config_path.read_bytes())
    if dataset not in config['datasets'] or recipe not in config['recipes']:raise ValueError('Outside catalogue')
    if smoke:
        config=dict(config,versions=[1],repetitions=1)
    sources=sorted((ROOT/'src/recoverml').glob('*.py'))+[Path(__file__).resolve(),WORKER,
               ROOT/'scripts/native_frontier_worker.py',config_path.resolve()]
    hashes={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sources}
    dump(output/'run_start.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dataset=dataset,recipe=recipe,smoke=smoke,config=config,source_sha256=hashes,timestamp_ns=time.time_ns()))
    with tarfile.open(output/'source_snapshot.tar.gz','w:gz') as t:
        for p in sources:t.add(p,arcname=p.relative_to(ROOT))
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
             MKL_NUM_THREADS='1',DVC_NO_ANALYTICS='true')
    # Native API stages spawn their own children, so their environment must
    # match explicit CLI subprocesses even while the API changes directory.
    for key in ('PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','DVC_NO_ANALYTICS'):
        os.environ[key]=env[key]
    rows=[];comparisons=[];retentions={}
    def invoke(args,cwd,label):
        start=time.perf_counter()
        result=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True)
        record=dict(label=label,command=args,returncode=result.returncode,elapsed_s=time.perf_counter()-start,
                    stdout=result.stdout,stderr=result.stderr)
        with (output/'commands.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        return record
    with threadpool_limits(limits=1):
        # Equal warm-import scope. Each API call still constructs its own repository/restorer.
        from dvc.repo import Repo
        logging.getLogger('dvc').setLevel(logging.ERROR)
        from recoverml.broad_workflows import execute
        from recoverml.file_recovery import recover_requested_files
        for versions in config['versions']:
            seed=config['seed_base']+DATASETS.index(dataset)*10000+RECIPES.index(recipe)*1000+versions
            g,info=capture(dataset,recipe,versions,seed)
            history=f'{dataset}-{recipe}-v{versions}'
            write_store(g,g.candidates,output/'captures'/history)
            dump(output/'captures'/history/'capture_info.json',info)
            for loss in config['losses']:
                caps,k,lost=capabilities(g,loss)
                selected,status,diag=optimize(g,caps,k,time_limit_s=120.)
                if status!='ok' or not diag.get('storage_optimal') or not diag.get('robust_certified'):
                    raise RuntimeError('Uncertified retention')
                for request_size in config['requests']:
                    ids=(list(g.targets[str(versions-1)]) if request_size=='latest'
                         else list(dict.fromkeys(t for ts in g.targets.values() for t in ts)))
                    targets={g.nodes[t].blob for t in ids}
                    key=f'{history}-{loss}-{request_size}'
                    retentions[key]=dict(history=history,selected=sorted(selected),capabilities=caps,k=k,disabled=lost,
                        targets=ids,common_bytes=retained_bytes(g,selected,caps,k),diagnostic=diag)
                    with tempfile.TemporaryDirectory(prefix='recoverml-census-') as tmp:
                        base=Path(tmp)
                        workspaces={m:base/m for m in config['methods']}
                        for w in workspaces.values():
                            write_store(g,selected,w)
                            (w/'outputs').mkdir()
                            (w/'capability_contract.json').write_bytes(contract(caps,k))
                            dump(w/'request.json',dict(targets=ids,disabled=lost))
                        native=workspaces['DVC_native']
                        selected_frontier=selected-g.roots
                        stages={}
                        for i,b in enumerate(sorted(selected_frontier)):
                            stages['paid_'+str(i)]=dict(cmd='exit 1',frozen=True,outs=['blobs/'+b+'.pkl'])
                        command=[sys.executable,str(WORKER),'--engine','direct_control','--workspace','.',
                                 '--receipt','worker.json']
                        cmd=subprocess.list2cmdline(command) if os.name=='nt' else shlex.join(command)
                        stages['recover_requested']=dict(cmd=cmd,
                            deps=['manifest.json','capability_contract.json','request.json',str(WORKER)]
                                +['blobs/'+b+'.pkl' for b in sorted(selected)],
                            outs=['outputs/'+b+'.pkl' for b in sorted(targets)])
                        (native/'dvc.yaml').write_text(yaml.safe_dump(dict(stages=stages),sort_keys=False))
                        for b in targets:(native/'outputs'/(b+'.pkl')).write_bytes(g.archive[b])
                        for args,label in [(['init','--no-scm','-q'],'init'),(['config','cache.type','copy'],'config'),
                                           (['commit','-f'],'commit')]:
                            r=invoke([sys.executable,'-m','dvc']+args,native,key+':'+label)
                            if r['returncode']:raise RuntimeError('Native setup failed: '+label)
                        layout={p.relative_to(native/'.dvc/cache').as_posix():digest(p.read_bytes())
                                for p in (native/'.dvc/cache').rglob('*')
                                if p.is_file() and digest(p.read_bytes()) in selected}
                        case_dir=output/'cases'/key;case_dir.mkdir(parents=True)
                        for p in ['dvc.yaml','dvc.lock']:shutil.copyfile(native/p,case_dir/p)
                        for interface in config['interfaces']:
                            case=f'{dataset}/{recipe}/v{versions}/{loss}/{request_size}/{interface}'
                            for repetition in range(config['repetitions']):
                                order=list(config['methods']);random.Random(case+str(repetition)).shuffle(order)
                                for position,method in enumerate(order):
                                    workspace=workspaces[method]
                                    for p in (workspace/'outputs').iterdir():
                                        if not p.is_file():raise RuntimeError('Unexpected output directory')
                                        p.unlink()
                                    worker=workspace/'worker.json'
                                    if worker.exists():worker.unlink()
                                    caches=reset_selected_cache(workspace/'.dvc/cache',workspace/'blobs',
                                                                 layout if method=='DVC_native' else {})
                                    payloads=list((workspace/'blobs').glob('*.pkl'))+[
                                        p for p in (workspace/'.dvc/cache').rglob('*') if p.is_file()]
                                    physical={(p.stat().st_dev,p.stat().st_ino):p.stat().st_size for p in payloads}
                                    paid=sum(g.sizes()[b] for b in selected)
                                    if set(caches)-selected or sum(physical.values())!=paid:
                                        raise RuntimeError('Unpaid initial cache or duplicate payload')
                                    all_retained=targets<=selected
                                    action='checkout' if all_retained else 'repro'
                                    started=time.perf_counter();ok=False;error=None;receipt=None;cmd_receipt=None
                                    captured=None;call_elapsed=None;verification_started=None
                                    try:
                                        if interface=='cli':
                                            if method=='DVC_native':
                                                args=[sys.executable,'-m','dvc',action,'recover_requested','-q']
                                                if action=='repro':args.append('--no-run-cache')
                                            else:
                                                args=[sys.executable,str(WORKER),'--engine',method,
                                                      '--workspace','.', '--receipt','worker.json']
                                            cmd_receipt=invoke(args,workspace,case+':'+method+':'+str(repetition))
                                            if cmd_receipt['returncode']:raise RuntimeError('Trial command failed')
                                        else:
                                            captured=io.StringIO()
                                            with contextlib.chdir(workspace), contextlib.redirect_stdout(captured),contextlib.redirect_stderr(captured):
                                                if method=='DVC_native':
                                                    with Repo(str(workspace)) as repo:
                                                        if all_retained:repo.checkout(targets=['recover_requested'])
                                                        else:repo.reproduce(targets=['recover_requested'],run_cache=False)
                                                else:receipt=recover(method,workspace)
                                        call_elapsed=(cmd_receipt['elapsed_s'] if interface=='cli'
                                                      else time.perf_counter()-started)
                                        verification_started=time.perf_counter()
                                        hashes_out={b:digest((workspace/'outputs'/(b+'.pkl')).read_bytes()) for b in targets}
                                        if set(p.stem for p in (workspace/'outputs').glob('*.pkl'))!=targets:
                                            raise RuntimeError('Wrong requested output inventory')
                                        ok=all(b==sha for b,sha in hashes_out.items())
                                        if not ok:raise RuntimeError('Target hash mismatch')
                                    except Exception as exc:
                                        error=repr(exc);hashes_out={}
                                    elapsed=(time.perf_counter()-started if call_elapsed is None else call_elapsed+
                                             (time.perf_counter()-verification_started))
                                    if captured is not None:
                                        with (output/'api_logs.jsonl').open('a') as log:
                                            log.write(json.dumps(dict(case=case,method=method,repetition=repetition,
                                                                      output=captured.getvalue()))+'\n')
                                    if worker.exists():receipt=json.loads(worker.read_bytes())
                                    operations=[] if receipt is None else receipt['operations']
                                    record=dict(case=case,method=method,repetition=repetition,order=position,
                                        elapsed_s=elapsed,ok=ok,error=error,target_sha256=hashes_out,
                                        retention_key=key,paid_payload_bytes=paid,unique_initial_payload_bytes=sum(physical.values()),
                                        cache_sha256=caches,initial_payloads=sorted(selected),outputs_initially_empty=True,
                                        native_action=action if method=='DVC_native' else None,
                                        worker_receipt=receipt,operations=operations)
                                    rows.append(record)
                                    with (output/'trials.jsonl').open('a') as f:f.write(json.dumps(record,allow_nan=False)+'\n')
                            current=[r for r in rows if r['case']==case]
                            medians={m:statistics.median(r['elapsed_s'] for r in current if r['method']==m)
                                     for m in config['methods']}
                            exact={m:all(r['ok'] for r in current if r['method']==m) for m in config['methods']}
                            ratio=medians['DVC_native']/medians['RecoverML']
                            comparisons.append(dict(case=case,median_s=medians,exact=exact,ratio_dvc_to_recoverml=ratio,
                                substantial_win=all(exact.values()) and ratio>=config['success']['minimum_case_speedup'],
                                all_requested_retained=all_retained,retention_key=key))
                            dump(output/'progress.json',dict(completed=len(comparisons),expected=len(catalogue(config,dataset,recipe))))
                            dump(output/'retentions.json',retentions)
                            print(case,ratio,exact,flush=True)
    with tarfile.open(output/'captures.tar.gz','w:gz') as t:t.add(output/'captures',arcname='captures')
    with tarfile.open(output/'cases.tar.gz','w:gz') as t:t.add(output/'cases',arcname='cases')
    changed=[p for p,sha in hashes.items() if digest((ROOT/p).read_bytes())!=sha]
    expected=set(catalogue(config,dataset,recipe))
    if {r['case'] for r in comparisons}!=expected:raise RuntimeError('Incomplete fixed catalogue')
    summary={i:dict(cases=sum(r['case'].endswith('/'+i) for r in comparisons),
        substantial_wins=sum(r['case'].endswith('/'+i) and r['substantial_win'] for r in comparisons),
        fraction=sum(r['case'].endswith('/'+i) and r['substantial_win'] for r in comparisons)/
                 sum(r['case'].endswith('/'+i) for r in comparisons)) for i in config['interfaces']}
    dump(output/'report.json',dict(status='PASS' if not changed and all(r['ok'] for r in rows) else 'FAIL',
        dataset=dataset,recipe=recipe,smoke=smoke,comparisons=comparisons,summary=summary,trials=len(rows),
        source_changed=changed,closed_sha256={p.name:digest(p.read_bytes()) for p in output.iterdir() if p.is_file()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--recipe',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,default=ROOT/'configs/recovery_census_oct26.json')
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args();run(args.output,args.protocol,args.dataset,args.recipe,args.smoke)
