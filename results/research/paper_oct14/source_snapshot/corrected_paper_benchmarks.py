"""Matched paper benchmarks with original-source and exact-formulation controls."""
import argparse
import csv
import gzip
import importlib.util
import itertools
import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph, RestoreError, digest, pack, write_store, environment
from . import operators  # Import before the recorded thread limit is applied.
from .witness_pipeline import capture
from .witness_optimizer import optimize as nominal
from .capability_retention import optimize, restricted, retained_bytes, contract, CapabilityRestorer
from .scenario_retention import optimize as expanded
from .published_materializers import load_source, select, REVISION, SOURCE_SHA256, URL
from .witness import certificate


def save(destination,rows,traces,report):
    if rows:
        with (destination/'summary.csv').open('w') as stream:
            keys=sorted(set().union(*(r.keys() for r in rows)))
            writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)
    raw=(json.dumps(traces,indent=2)+'\n').encode()
    (destination/'execution_traces.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    report.update(trace_sha256=digest(raw),source_sha256=digest(Path(__file__).read_bytes()),
        source_dependencies={name:digest(Path(__file__).with_name(name).read_bytes()) for name in
            ('witness.py','witness_pipeline.py','capability_retention.py','scenario_retention.py','published_materializers.py','capability_ops.py')},
        process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        environment=environment())
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def recovery_matrix(destination,suite,seeds=2,versions=12,hyppo_cache=None):
    destination.mkdir(parents=True,exist_ok=False)
    module=load_source(hyppo_cache or destination/'original_source')
    workloads=([(d,'logistic',fmt) for d in ('breast_cancer','iris','wine','banknote') for fmt in ('npy','csv6')]
               if suite=='tabular' else [('digits',m,'npy') for m in ('forest','mlp')])
    rows,traces,plans,quality=[],[],[],[]
    with threadpool_limits(limits=1):
        for name,model,fmt in workloads:
            for seed in range(seeds):
                graph,info=capture(name,seed,fmt,versions,dual_scalers=True,estimator=model)
                quality.append(dict(dataset=name,estimator=model,seed=seed,format=fmt,**{'accuracy':info['accuracy']}))
                families={'split':'membership','fit_scaler':'sklearn_preprocessing',
                          'scale_sklearn':'sklearn_preprocessing','scale':'numpy_scaling'}
                caps={nid:families[n.op] for nid,n in graph.nodes.items() if n.op in families and n.replayable}
                groups=sorted(set(caps.values()))
                small,status,diag=nominal(graph,time_limit_s=30.)
                if status!='ok' or not diag['storage_optimal']:raise RuntimeError('Nominal optimum missing')
                conservative,cs,cd=nominal(restricted(graph,caps,groups),time_limit_s=30.)
                if cs!='ok' or not cd['storage_optimal']:raise RuntimeError('Conservative optimum missing')
                snapshot=graph.roots|{graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
                for k in (1,2):
                    case=f'{name}-{model}-{seed:02d}-{fmt}-k{k}'
                    robust,status,rd=optimize(graph,caps,k,time_limit_s=30.)
                    explicit,es,ed=expanded(graph,caps,k,time_limit_s=30.)
                    if status!='ok' or not rd['storage_optimal'] or es!='ok' or not ed['storage_optimal']:
                        raise RuntimeError('Exact comparison incomplete '+case)
                    budget=retained_bytes(graph,robust,caps,k)
                    if budget!=retained_bytes(graph,explicit,caps,k):raise RuntimeError('Independent optima disagree')
                    optional=budget-retained_bytes(graph,graph.roots,caps,k)
                    policies={'robust':robust,'expanded_exact':explicit,'nominal':small,
                        'all_groups_off':conservative,'snapshots':snapshot,
                        'HYPPO_rank_component':select(graph,optional,module),
                        'HYPPO_frequency_component':select(graph,optional,module,frequency=True)}
                    snapshot_optional=retained_bytes(graph,snapshot,caps,k)-retained_bytes(graph,graph.roots,caps,k)
                    policies.update(HYPPO_rank_snapshot_budget=select(graph,snapshot_optional,module),
                        HYPPO_frequency_snapshot_budget=select(graph,snapshot_optional,module,frequency=True))
                    faults=[tuple(f) for i in range(k+1) for f in itertools.combinations(groups,i)]
                    for policy,selected in policies.items():
                        store=destination/'stores'/case/policy;write_store(graph,selected,store)
                        (store/'capability_contract.json').write_bytes(contract(caps,k))
                        total=retained_bytes(graph,selected,caps,k)
                        if sum(p.stat().st_size for p in store.rglob('*') if p.is_file())!=total:raise RuntimeError('Byte mismatch')
                        attempts=exact=blocked=0;latency=[];cpu=[]
                        for lost in faults:
                            disk=Graph.read(store/'manifest.json');coverage=certificate(restricted(disk,caps,lost),selected)['version_coverage']
                            for version,targets in graph.targets.items():
                                restorer=CapabilityRestorer(disk,store,caps,lost)
                                start=time.time_ns();clock=time.perf_counter();work=time.process_time();ok=False;error=None
                                try:
                                    values=restorer.version(version)
                                    ok=all(pack(v)==graph.archive[graph.nodes[t].blob] for v,t in zip(values,targets))
                                    if not ok:raise RuntimeError('Target mismatch')
                                except RestoreError as exc:
                                    if coverage[version]:raise RuntimeError('Unexpected structural recovery failure') from exc
                                    error=str(exc)
                                elapsed=time.perf_counter()-clock;used=time.process_time()-work
                                if any(e.get('producer') and caps.get(e['producer']) in lost for e in restorer.trace):raise RuntimeError('Disabled producer executed')
                                attempts+=1;exact+=int(ok);blocked+=int(error is not None)
                                if ok:latency.append(elapsed);cpu.append(used)
                                traces.append(dict(case=case,policy=policy,version=version,disabled=list(lost),
                                    start_timestamp_ns=start,end_timestamp_ns=time.time_ns(),latency_s=elapsed,cpu_s=used,
                                    exact=ok,expected_blocked=error is not None,error=error,events=restorer.trace,capture_archive_absent=not disk.archive))
                        if policy in ('robust','expanded_exact','all_groups_off','snapshots') and exact!=attempts:raise RuntimeError('Safe policy failed')
                        rows.append(dict(case=case,dataset=name,estimator=model,seed=seed,format=fmt,k=k,versions=versions,
                            policy=policy,retained_bytes=total,robust_budget=budget,snapshot_bytes=retained_bytes(graph,snapshot,caps,k),
                            within_robust_budget=total<=budget,requests=attempts,exact=exact,blocked=blocked,
                            median_success_latency_s=statistics.median(latency) if latency else None,
                            median_success_cpu_s=statistics.median(cpu) if cpu else None,
                            saving_vs_snapshots=100*(1-total/retained_bytes(graph,snapshot,caps,k))))
                    plans.append(dict(case=case,robust=rd,expanded=ed,retained={p:sorted(s) for p,s in policies.items()},capabilities=caps))
                    print(json.dumps(dict(completed_case=case,robust_bytes=budget)),flush=True)
    (destination/'planner_certificates.json.gz').write_bytes(gzip.compress((json.dumps(plans,indent=2)+'\n').encode(),mtime=0))
    return save(destination,rows,traces,dict(suite=suite,planning_cases=len(plans),captured_histories=len(quality),
        requests=len(traces),exact=sum(t['exact'] for t in traces),expected_blocked=sum(t['expected_blocked'] for t in traces),
        quality=quality,hyppo_revision=REVISION,hyppo_source_sha256=SOURCE_SHA256,hyppo_url=URL,
        comparison_scope='Original HYPPO materialization component with our physical-blob and ancestry-cost adapter and common exact executor; not a full-system HYPPO comparison',
        fault_scope='Injected replay call restrictions; intact files and numerical environment and training/prediction remain available'))


def scaling(destination,trials=3):
    from .capability_scaling import build
    destination.mkdir(parents=True,exist_ok=False);rows,traces=[],[]
    with threadpool_limits(limits=1):
        for groups in (6,12,24):
            for k in (1,2):
                graph,caps,analytic,_=build(groups,k,width=16)
                for trial in range(trials):
                    order=[('counterexample',optimize),('expanded_exact',expanded)]
                    if trial%2:order.reverse()
                    for name,solver in order:
                        start=time.time_ns();clock=time.perf_counter();cpu=time.process_time()
                        chosen,status,diag=solver(graph,caps,k,time_limit_s=30.)
                        elapsed=time.perf_counter()-clock;used=time.process_time()-cpu
                        verified=status=='ok' and diag['storage_optimal'] and retained_bytes(graph,chosen,caps,k)==analytic
                        if status=='ok' and not verified:raise RuntimeError('Analytic optimum mismatch')
                        rows.append(dict(groups=groups,k=k,trial=trial,policy=name,status=status,elapsed_s=elapsed,cpu_s=used,
                            analytic_match=verified,scenarios=sum(__import__('math').comb(groups,i) for i in range(k+1)),
                            master_variables=diag.get('master_storage_variables'),variables=diag.get('variables'),
                            oracle_calls=len(diag.get('iterations',[])),retained_bytes=retained_bytes(graph,chosen,caps,k)))
                        traces.append(dict(start_timestamp_ns=start,end_timestamp_ns=time.time_ns(),**rows[-1],diagnostic=diag))
                        print(json.dumps(rows[-1]),flush=True)
    return save(destination,rows,traces,dict(suite='scaling',planner_runs=len(rows),
        certified_matches=sum(r['analytic_match'] for r in rows),qualification='Generated analytic family and rotated timing order; total construction and solving time included'))


def dvc_snapshots(destination,seeds=2):
    destination.mkdir(parents=True,exist_ok=False);rows,traces=[],[]
    env={**os.environ,'DVC_NO_ANALYTICS':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    def command(directory,*args):
        start=time.time_ns();before=resource.getrusage(resource.RUSAGE_CHILDREN)
        result=subprocess.run([sys.executable,'-m','dvc',*args],cwd=directory,env=env,text=True,capture_output=True,timeout=120)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        traces.append(dict(command=['python','-m','dvc',*args],start_timestamp_ns=start,end_timestamp_ns=time.time_ns(),
            returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
            child_cpu_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime))
        if result.returncode:raise RuntimeError(result.stderr)
    with threadpool_limits(limits=1):
        for dataset,model,versions in [('banknote','logistic',12),('digits','forest',4),('digits','mlp',4)]:
            for seed in range(seeds):
                graph,info=capture(dataset,seed,'npy',versions,dual_scalers=True,estimator=model)
                families={'split':'membership','fit_scaler':'sklearn_preprocessing','scale_sklearn':'sklearn_preprocessing','scale':'numpy_scaling'}
                caps={nid:families[n.op] for nid,n in graph.nodes.items() if n.op in families and n.replayable}
                protected=graph.roots|{graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
                with tempfile.TemporaryDirectory(prefix='recoverml_native_dvc_') as temp:
                    repo=Path(temp);command(repo,'init','--no-scm');command(repo,'config','core.analytics','false')
                    inputs=repo/'inputs';inputs.mkdir()
                    for blob in graph.roots:(inputs/(blob+'.pkl')).write_bytes(graph.archive[blob])
                    command(repo,'add','inputs')
                    for version,targets in graph.targets.items():
                        directory=repo/'versions'/('v'+version);directory.mkdir(parents=True)
                        for target in targets:
                            blob=graph.nodes[target].blob;(directory/(blob+'.pkl')).write_bytes(graph.archive[blob])
                        command(repo,'add',str(directory.relative_to(repo)))
                    object_files=[p for p in (repo/'.dvc/cache/files/md5').rglob('*') if p.is_file()]
                    payload_bytes=sum(p.stat().st_size for p in object_files if p.suffix!='.dir')
                    if payload_bytes!=sum(graph.sizes()[b] for b in protected):raise RuntimeError('DVC data payload differs')
                    native_bytes=sum(p.stat().st_size for p in object_files)+sum(p.stat().st_size for p in repo.rglob('*.dvc') if p.is_file())
                    for version,targets in graph.targets.items():
                        directory=repo/'versions'/('v'+version)
                        shutil.rmtree(directory);command(repo,'checkout',str(directory.relative_to(repo))+'.dvc')
                        if not all(digest((directory/(graph.nodes[t].blob+'.pkl')).read_bytes())==graph.nodes[t].blob for t in targets):raise RuntimeError('DVC target mismatch')
                    for k in (1,2):
                        chosen,status,diag=optimize(graph,caps,k,time_limit_s=30.)
                        if status!='ok' or not diag['storage_optimal']:raise RuntimeError('Robust optimum missing')
                        common_metadata=graph.metadata_bytes()+len(contract(caps,k))
                        common_snapshot=common_metadata+payload_bytes;robust=retained_bytes(graph,chosen,caps,k)
                        rows.append(dict(dataset=dataset,estimator=model,seed=seed,versions=versions,k=k,
                            dvc_version=__import__('importlib.metadata',fromlist=['version']).version('dvc'),native_object_and_pointer_bytes=native_bytes,
                            common_snapshot_bytes=common_snapshot,robust_bytes=robust,saving_normalized=100*(1-robust/common_snapshot),
                            exact_disk_checkouts=versions,scope='Native DVC snapshot checkout; common payload accounting separates DVC-specific directory and pointer overhead'))
    return save(destination,rows,traces,dict(suite='dvc',cases=len(rows),
        actual_checkouts=sum(r['exact_disk_checkouts'] for r in rows)//2,
        comparison_scope='Native DVC immutable snapshots with exact hash validation; no claim about DVC repro execution or DVC speed superiority'))


def index_benchmark(destination,scan_source,trials=5):
    destination.mkdir(parents=True,exist_ok=False);rows,traces=[],[]
    spec=importlib.util.spec_from_file_location('recoverml._scan_reference',scan_source)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    for depth in (32,128,512,2048):
        g=Graph(env={});node=g.add('input',[],{},0,False,'source',0,0,mandatory=True)
        for i in range(depth):node=g.add('affine_features',[node],{'scale':1,'offset':1},i+1,True,'chain',.01,0)
        g.targets={'0':[node]};expected=old.certificate(g,g.roots)
        if certificate(g,g.roots)!=expected:raise RuntimeError('Certificate changed')
        for trial in range(trials):
            order=[('scan',old.certificate),('indexed',certificate)]
            if trial%2:order.reverse()
            for name,fn in order:
                start=time.time_ns();clock=time.perf_counter();work=time.process_time();answer=fn(g,g.roots)
                elapsed=time.perf_counter()-clock;cpu=time.process_time()-work
                if answer!=expected:raise RuntimeError('Producer certificate changed')
                rows.append(dict(depth=depth,trial=trial,policy=name,elapsed_s=elapsed,cpu_s=cpu,identical_certificate=True))
                traces.append(dict(**rows[-1],start_timestamp_ns=start,end_timestamp_ns=time.time_ns()))
    return save(destination,rows,traces,dict(suite='index',runs=len(rows),reference_sha256=digest(Path(scan_source).read_bytes()),
        qualification='Synthetic dependency chains and certificate kernel only; not full recovery latency'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--suite',choices=['tabular','neural','scaling','dvc','index'],required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--seeds',type=int,default=2)
    parser.add_argument('--versions',type=int,default=12);parser.add_argument('--trials',type=int,default=3)
    parser.add_argument('--hyppo-cache',type=Path);parser.add_argument('--scan-source',type=Path)
    args=parser.parse_args()
    if args.suite in ('tabular','neural'):report=recovery_matrix(args.output,args.suite,args.seeds,args.versions,args.hyppo_cache)
    elif args.suite=='scaling':report=scaling(args.output,args.trials)
    elif args.suite=='dvc':report=dvc_snapshots(args.output,args.seeds)
    else:
        if not args.scan_source:parser.error('--scan-source required')
        report=index_benchmark(args.output,args.scan_source,args.trials)
    print(json.dumps({k:v for k,v in report.items() if k not in ('quality','environment','source_dependencies')},indent=2))
