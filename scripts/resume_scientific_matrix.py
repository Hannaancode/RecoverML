"""Resume an interrupted declared matrix without choosing cases by outcome.

Use --prepare first, then twelve --case invocations against the frozen captures.
Worker command logs and exit codes belong to the orchestrator, not this module.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
import csv
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from recoverml.core import Graph,digest,environment,write_store
from recoverml.robust_heuristics import fault_sets
from recoverml.scientific_workflows import caps_for,capture
from recoverml.scientific_benchmarks import dump,run
from threadpoolctl import threadpool_limits


def readable_records(path):
    """Return only complete JSON lines and disclose truncated compression."""
    records=[];error=None
    try:
        with gzip.open(path,'rt') as stream:
            for line in stream:
                try:record=json.loads(line)
                except json.JSONDecodeError as exc:
                    error=repr(exc);break
                records.append(record)
    except (EOFError,OSError) as exc:error=repr(exc)
    return records,error


def request_identity(record):
    return (record['case'],record['policy'],float(record['budget_fraction']),
            str(record['version']),tuple(record['disabled']))


def declared_history_identities(protocol,history,graph):
    return {(f'{history}-{scope}-k{k}',method,float(budget),str(version),tuple(lost))
            for scope,k,budget,method in itertools.product(protocol['capability_scopes'],
                protocol['loss_bounds'],protocol['optional_snapshot_budget_fractions'],protocol['methods'])
            for lost in fault_sets(caps_for(graph,scope),k) for version in graph.targets}


def select_complete_original(protocol,original,rows,traces,allowed_workflows):
    """A full manifest-derived grid is the sole criterion for history reuse."""
    chosen=[];selected_rows=[];selected_traces=[];diagnostics=[]
    for workflow,seed in itertools.product(protocol['workflows'],protocol['seeds']):
        history=f'{workflow}-{seed}'
        if workflow not in allowed_workflows:continue
        graph=Graph.read(original/'captures'/history/'manifest.json')
        rs=[r for r in rows if r['history']==history]
        ts=[t for t in traces if t['history']==history]
        expected=declared_history_identities(protocol,history,graph)
        actual=[request_identity(t) for t in ts]
        expected_rows={(f'{history}-{scope}-k{k}',method,float(budget))
            for scope,k,budget,method in itertools.product(protocol['capability_scopes'],
                protocol['loss_bounds'],protocol['optional_snapshot_budget_fractions'],protocol['methods'])}
        actual_rows=[(r['case'],r['policy'],float(r['budget_fraction'])) for r in rs]
        if set(actual)!=expected or len(actual)!=len(expected):
            raise RuntimeError('Declared request grid incomplete or duplicated: '+history)
        if set(actual_rows)!=expected_rows or len(actual_rows)!=len(expected_rows):
            raise RuntimeError('Declared summary grid incomplete or duplicated: '+history)
        counts={}
        for t in ts:
            key=request_identity(t)[:3];c=counts.setdefault(key,Counter())
            for name in ('exact','expected_blocked','unexpected'):c[name]+=int(t[name])
            c['requests']+=1
        for r in rs:
            key=(r['case'],r['policy'],float(r['budget_fraction']));c=counts[key]
            for field,raw in [('requests','requests'),('exact','exact'),('blocked','expected_blocked'),('unexpected','unexpected')]:
                if int(r[field])!=c[raw]:raise RuntimeError('Summary/raw mismatch: '+str(key))
        chosen.append(history);selected_rows+=rs;selected_traces+=ts
        diagnostics.append(dict(history=history,rows=len(rs),requests=len(ts),
            expected_request_identities=len(expected),complete=True,
            selection_basis='All declared identities and counts present; no performance or recovery outcome filtering'))
    return chosen,selected_rows,selected_traces,diagnostics


def prepare(destination,resume_path):
    destination=destination.resolve()
    destination.mkdir(parents=True,exist_ok=False)
    resume=json.loads(resume_path.read_text());original=ROOT/resume['original_directory']
    protocol=json.loads((ROOT/resume['original_protocol']).read_text())
    for key,name in [('original_summary_sha256','summary.csv'),('original_trace_sha256','execution_traces.jsonl.gz')]:
        if digest((original/name).read_bytes())!=resume[key]:raise RuntimeError('Original evidence changed')
    dump(destination/'resume_protocol.json',resume);dump(destination/'protocol.json',protocol)
    rows=list(csv.DictReader((original/'summary.csv').open()));traces,error=readable_records(original/'execution_traces.jsonl.gz')
    histories,_,_,details=select_complete_original(protocol,original,rows,traces,resume['reused_workflows'])
    dump(destination/'interruption_inventory.json',dict(original_summary_rows=len(rows),readable_raw_records=len(traces),
        gzip_read_error=error,original_files_unchanged=True,reused_histories=histories,
        reused_history_grid_checks=details,excluded_partial_histories=sorted({r['history'] for r in rows}-set(histories)),
        exclusion_reason='Entire forest recipe rerun under the frozen protocol, independent of outcome'))
    sources=destination/'source_snapshot';sources.mkdir();source_hashes={}
    for source in sorted((ROOT/'src/recoverml').glob('*.py')):
        shutil.copyfile(source,sources/source.name);source_hashes[source.name]=digest(source.read_bytes())
    dump(destination/'prepare_start.json',dict(timestamp_ns=time.time_ns(),environment=environment(),
        protocol_sha256=digest(resume_path.read_bytes()),git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        source_sha256=source_hashes))
    captures=[]
    with threadpool_limits(limits=1):
        for workflow,seed in itertools.product(resume['rerun_workflows'],resume['rerun_seeds']):
            history=f'{workflow}-{seed}';clock=time.perf_counter()
            graph,info=capture(workflow,seed,protocol['versions']);seconds=time.perf_counter()-clock
            path=destination/'captures'/history;write_store(graph,graph.candidates,path)
            dump(path/'capture_info.json',info)
            captures.append(dict(history=history,capture_s=seconds,manifest_sha256=digest((path/'manifest.json').read_bytes()),**info))
            dump(destination/'fresh_capture_inventory.json',captures)
            print(json.dumps(dict(captured=history,capture_s=seconds,largest_model_bytes=info['largest_model_bytes'])),flush=True)
    finish_preparation(destination)


def finish_preparation(destination):
    """Complete only bookkeeping after a capture-stage command was interrupted."""
    destination=destination.resolve()
    resume=json.loads((destination/'resume_protocol.json').read_text())
    protocol=json.loads((destination/'protocol.json').read_text())
    captures=json.loads((destination/'fresh_capture_inventory.json').read_text())
    if {i['history'] for i in captures}!={f'{w}-{s}' for w,s in itertools.product(resume['rerun_workflows'],resume['rerun_seeds'])}:
        raise RuntimeError('Fresh captured history grid incomplete')
    for item in captures:
        path=destination/'captures'/item['history']
        if digest((path/'manifest.json').read_bytes())!=item['manifest_sha256']:raise RuntimeError('Fresh manifest changed')
    source_hashes=json.loads((destination/'prepare_start.json').read_text())['source_sha256']
    derived=[]
    for workflow,seed,scope,k in itertools.product(resume['rerun_workflows'],resume['rerun_seeds'],
            protocol['capability_scopes'],protocol['loss_bounds']):
        case=f'{workflow}-{seed}-{scope}-k{k}';config=dict(protocol)
        config.update(workflows=[workflow],seeds=[seed],capability_scopes=[scope],loss_bounds=[k])
        path=destination/'case_protocols'/(case+'.json');path.parent.mkdir(exist_ok=True);dump(path,config)
        derived.append(dict(case=case,protocol=str(path.relative_to(ROOT)),protocol_sha256=digest(path.read_bytes())))
    dump(destination/'case_inventory.json',derived)
    changed=[name for name,h in source_hashes.items() if digest((ROOT/'src/recoverml'/name).read_bytes())!=h]
    dump(destination/'prepare_report.json',dict(status='PASS' if not changed else 'FAIL',fresh_histories=len(captures),
        source_changed_during_capture=changed,finish_timestamp_ns=time.time_ns()))
    if changed:raise RuntimeError('Source changed during fresh capture')


def case_run(destination,case,hyppo_cache):
    item=next(x for x in json.loads((destination/'case_inventory.json').read_text()) if x['case']==case)
    protocol=ROOT/item['protocol']
    if digest(protocol.read_bytes())!=item['protocol_sha256']:raise RuntimeError('Derived case protocol changed')
    return run(destination/'cases'/case,protocol,hyppo_cache,capture_input=destination/'captures')


def all_cases(destination,hyppo_cache):
    """Run the fixed case list with the prospectively disclosed concurrency."""
    resume=json.loads((destination/'resume_protocol.json').read_text())
    items=json.loads((destination/'case_inventory.json').read_text());receipts=[]
    logs=destination/'worker_logs';logs.mkdir(exist_ok=False)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=str(ROOT/'src'))
    def worker(item):
        command=[sys.executable,str(Path(__file__).resolve()),'--output',str(destination.resolve()),
            '--case',item['case'],'--hyppo-cache',str(hyppo_cache.resolve())]
        started=time.time_ns()
        with (logs/(item['case']+'.txt')).open('w') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        receipt=dict(case=item['case'],command=command,start_timestamp_ns=started,end_timestamp_ns=time.time_ns(),exit_code=result.returncode)
        dump(logs/(item['case']+'.json'),receipt)
        return receipt
    with ThreadPoolExecutor(max_workers=resume['case_workers']) as pool:
        jobs=[pool.submit(worker,item) for item in items]
        for job in as_completed(jobs):
            receipt=job.result();receipts.append(receipt);dump(destination/'worker_execution.json',receipts)
            print(json.dumps(receipt),flush=True)
    if any(r['exit_code'] for r in receipts):raise RuntimeError('A declared worker failed; see complete preserved logs')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,default=ROOT/'configs/scientific_resume_oct15.json')
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--case')
    parser.add_argument('--run-cases',action='store_true')
    parser.add_argument('--finish-preparation',action='store_true')
    parser.add_argument('--hyppo-cache',type=Path,default=ROOT.parent/'baseline_sources/HYPPO/Components')
    args=parser.parse_args()
    if args.prepare:prepare(args.output,args.protocol)
    elif args.finish_preparation:finish_preparation(args.output)
    elif args.run_cases:all_cases(args.output,args.hyppo_cache)
    elif args.case:print(json.dumps(case_run(args.output,args.case,args.hyppo_cache),indent=2))
    else:parser.error('Specify --prepare or --case')
