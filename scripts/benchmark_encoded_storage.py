"""Fixed full-catalogue lossless storage experiment; all blocks and failures retained."""
import argparse
import gzip
import itertools
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import time
import traceback
import zlib

from threadpoolctl import threadpool_limits
from recoverml.core import canonical,digest,write_store
from recoverml.capability_retention import contract,retained_bytes,restricted
from recoverml.component_retention import optimize
from recoverml.scenario_retention import optimize as reference
from recoverml.robust_heuristics import fault_sets,select as local
from recoverml.published_materializers import load_source,select as hyppo,REVISION,SOURCE_SHA256
from recoverml.helix_materializer import select as helix
from recoverml.broad_workflows import capture,capabilities,execute,DATASETS,RECIPES
from recoverml.encoded_store import Representation,EncodedStore,metadata
from recoverml.file_recovery import recover_requested_files
from recoverml.witness import certificate

ROOT=Path(__file__).resolve().parents[1]


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def run(output,config_path,dataset,recipe,hyppo_cache,smoke=False):
    output.mkdir(parents=True,exist_ok=False)
    config=json.loads(config_path.read_bytes())
    if dataset not in config['datasets'] or recipe not in config['recipes']:raise ValueError('Outside fixed catalogue')
    if smoke:config=dict(config,versions=[1])
    source_paths=sorted((ROOT/'src/recoverml').glob('*.py'))+[Path(__file__).resolve(),config_path.resolve()]
    hashes={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in source_paths}
    dump(output/'run_start.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dataset=dataset,recipe=recipe,smoke=smoke,config=config,source_sha256=hashes,timestamp_ns=time.time_ns(),
        hyppo_revision=REVISION,hyppo_source_sha256=SOURCE_SHA256,
        platform=platform.platform(),zlib_build=zlib.ZLIB_VERSION,zlib_runtime=zlib.ZLIB_RUNTIME_VERSION))
    with tarfile.open(output/'source_snapshot.tar.gz','w:gz') as archive:
        for path in source_paths:archive.add(path,arcname=path.relative_to(ROOT))
    objects=output/'objects';objects.mkdir()
    def put(raw):
        identity=digest(raw);path=objects/(identity+'.bin')
        if path.exists():
            if path.read_bytes()!=raw:raise RuntimeError('Content identity collision')
        else:path.write_bytes(raw)
        return identity
    module=load_source(hyppo_cache)
    captures=[];plans=[];trials=[];comparisons=[]
    def flush():
        dump(output/'captures.json',captures);dump(output/'plans.json',plans)
        dump(output/'comparisons.json',comparisons)
        dump(output/'progress.json',dict(conditions=len(comparisons),requests=len(trials),
                                        unexpected=sum(t['unexpected'] for t in trials)))
    with threadpool_limits(limits=1),gzip.open(output/'trials.jsonl.gz','wt',encoding='utf-8') as trace:
        for versions in config['versions']:
            seed=config['seed_base']+DATASETS.index(dataset)*10000+RECIPES.index(recipe)*1000+versions
            graph,info=capture(dataset,recipe,versions,seed)
            history=f'{dataset}/{recipe}/v{versions}'
            adaptive=Representation(graph,policy='adaptive');gz=Representation(graph,policy='gzip9')
            captures.append(dict(history=history,info=info,manifest=put(canonical(graph.manifest())),
                payloads={b:dict(raw_bytes=graph.sizes()[b],adaptive=put(adaptive.encoded[b]),gzip9=put(gz.encoded[b]))
                          for b in sorted(graph.candidates)}))
            requested=list(dict.fromkeys(t for v in sorted(graph.targets,key=int) for t in graph.targets[v]))
            target_blobs={graph.nodes[t].blob for t in requested}
            for loss in config['losses']:
                case=history+'/'+loss;caps,k,_=capabilities(graph,loss);faults=fault_sets(caps,k)
                chosen={};diagnostics={};reference_choices={}
                for name,g in [('raw_exact',graph),('gzip_exact',gz.cost_graph),('adaptive_exact',adaptive.cost_graph)]:
                    chosen[name],status,diag=optimize(g,caps,k,time_limit_s=config['solver_time_limit_s'])
                    other,ref_status,ref_diag=reference(g,caps,k,time_limit_s=config['solver_time_limit_s'])
                    if (status!='ok' or ref_status!='ok' or not diag.get('storage_optimal') or
                        not ref_diag.get('storage_optimal') or retained_bytes(g,chosen[name],caps,k)!=retained_bytes(g,other,caps,k)):
                        raise RuntimeError('Uncertified or disagreeing exact objective: '+case+'/'+name)
                    diagnostics[name]=dict(status=status,diagnostic=diag,reference_diagnostic=ref_diag)
                    reference_choices[name]=sorted(other)
                view=adaptive.cost_graph
                chosen['adaptive_local'],diagnostics['adaptive_local']=local(view,caps,k,retained_bytes(view,view.candidates,caps,k),True)
                chosen['adaptive_snapshots']=graph.roots|target_blobs
                chosen['adaptive_raw_choice']=set(chosen['raw_exact'])
                optional=sum(view.sizes()[b] for b in chosen['adaptive_exact']-graph.roots)
                chosen['HYPPO_rank']=hyppo(view,optional,module,False)
                chosen['HYPPO_frequency']=hyppo(view,optional,module,True)
                chosen['HELIX_rule'],diagnostics['HELIX_rule']=helix(view,optional,config['helix_read_MiB_s']*1024**2)
                common_metadata=put(metadata(graph,caps,k,'adaptive'))
                sizes={}
                for method in config['methods']:
                    selected=set(chosen[method]);representation=gz if method=='gzip_exact' else adaptive
                    certificates=[dict(disabled=list(f),certificate=certificate(restricted(graph,caps,f),selected)) for f in faults]
                    complete=all(c['certificate']['complete'] for c in certificates)
                    if method in config['robust_methods'] and not complete:raise RuntimeError('Robust method failed closure')
                    if method.startswith('HYPPO') or method=='HELIX_rule':
                        if sum(view.sizes()[b] for b in selected-graph.roots)>optional:raise RuntimeError('Adapter exceeded common budget')
                    with tempfile.TemporaryDirectory(prefix='recoverml-encoded-') as temporary:
                        base=Path(temporary);store=base/'store'
                        if method=='raw_exact':
                            write_store(graph,selected,store);(store/'capability_contract.json').write_bytes(contract(caps,k))
                            expected_size=retained_bytes(graph,selected,caps,k)
                        else:expected_size=representation.write(selected,caps,k,store)
                        inventory={p.relative_to(store).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes()))
                                   for p in store.rglob('*') if p.is_file()}
                        actual=sum(item['bytes'] for item in inventory.values())
                        if actual!=expected_size:raise RuntimeError('Actual store bytes differ')
                        sizes[method]=actual
                        plans.append(dict(case=case,method=method,selected=sorted(selected),actual_bytes=actual,
                            metadata_object=common_metadata if method!='raw_exact' else None,inventory=inventory,
                            robust=complete,certificates=certificates,optional_budget=optional,
                            diagnostic=diagnostics.get(method),reference_selected=reference_choices.get(method)))
                        for index,lost in enumerate(faults):
                            expected=certificates[index]['certificate']['complete'];output_dir=base/('out'+str(index))
                            clock=time.perf_counter();receipt=None;error=None
                            try:
                                if method=='raw_exact':
                                    receipt=recover_requested_files(store,output_dir,target_ids=requested,disabled=lost,replay_execute=execute)
                                else:receipt=EncodedStore(store).recover(output_dir,target_ids=requested,disabled=lost,replay_execute=execute)
                            except Exception as exc:error=type(exc).__name__+': '+str(exc)
                            elapsed=time.perf_counter()-clock
                            found={p.stem:digest(p.read_bytes()) for p in output_dir.glob('*.pkl')}
                            partial_valid=set(found)<=target_blobs and all(b==sha for b,sha in found.items())
                            ok=error is None and receipt is not None and found=={b:b for b in target_blobs}
                            blocked=not expected and error is not None and 'No grounded alternative producer' in error and partial_valid
                            unexpected=(expected and not ok) or (not expected and not blocked)
                            row=dict(case=case,method=method,disabled=list(lost),expected_complete=expected,
                                ok=ok,expected_blocked=blocked,unexpected=unexpected,error=error,
                                elapsed_s=elapsed,initial_outputs_empty=True,output_sha256=found,
                                receipt=receipt,operations=[] if receipt is None else receipt['operations'])
                            trials.append(row);trace.write(json.dumps(row,allow_nan=False)+'\n');trace.flush()
                comparisons.append(dict(case=case,sizes=sizes,
                    saving_vs_raw=1-sizes['adaptive_exact']/sizes['raw_exact'],
                    saving_vs_gzip=1-sizes['adaptive_exact']/sizes['gzip_exact'],
                    saving_from_reselection=1-sizes['adaptive_exact']/sizes['adaptive_raw_choice'],
                    manual_oracle_bytes=adaptive.size(set(reference_choices['adaptive_exact']),caps,k)))
                flush();print(case,json.dumps(comparisons[-1]),flush=True)
    with tarfile.open(output/'objects.tar.gz','w:gz') as archive:
        for path in sorted(objects.iterdir()):archive.add(path,arcname=path.name)
    changed=[p for p,sha in hashes.items() if digest((ROOT/p).read_bytes())!=sha]
    dump(output/'report.json',dict(status='PASS' if not changed and not any(t['unexpected'] for t in trials) else 'FAIL',
        conditions=len(comparisons),requests=len(trials),source_changed=changed,
        unexpected=sum(t['unexpected'] for t in trials),expected_blocks=sum(t['expected_blocked'] for t in trials),
        closed_sha256={p.name:digest(p.read_bytes()) for p in output.iterdir() if p.is_file()}))
    if changed or any(t['unexpected'] for t in trials):raise RuntimeError('Unexpected experiment outcome')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True);parser.add_argument('--recipe',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,default=ROOT/'configs/encoded_storage_oct26.json')
    parser.add_argument('--hyppo-cache',type=Path,default=ROOT/'work/pinned_hyppo_encoded')
    parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    try:run(args.output,args.protocol,args.dataset,args.recipe,args.hyppo_cache,args.smoke)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
