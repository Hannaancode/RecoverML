"""One mixed real-workload retention problem spanning 112 historical versions."""
import argparse
import gzip
import itertools
import json
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,pack,digest,write_store
from . import operators
from .witness_pipeline import capture
from .capability_retention import optimize,contract,retained_bytes,CapabilityRestorer
from .scenario_retention import optimize as expanded


def run(destination):
    destination.mkdir(parents=True,exist_ok=False);rows=[];traces=[];planning=[]
    with threadpool_limits(limits=1):
        graph=Graph();branches=[]
        workloads=[(d,'logistic',12) for d in ('breast_cancer','iris','wine','banknote')]+[('digits',m,4) for m in ('forest','mlp')]
        for dataset,model,versions in workloads:
            for seed in (0,1):
                branch,info=capture(dataset,seed,'npy',versions,dual_scalers=True,estimator=model)
                if branch.env!=graph.env:raise RuntimeError('Mixed environment')
                for nid,node in branch.nodes.items():
                    if nid in graph.nodes:
                        old=graph.nodes[nid]
                        if (old.op,old.deps,old.params,old.blob,old.replayable)!=(node.op,node.deps,node.params,node.blob,node.replayable):raise RuntimeError('Logical identity collision')
                    else:graph.nodes[nid]=node
                for blob,raw in branch.archive.items():
                    if blob in graph.archive and graph.archive[blob]!=raw:raise RuntimeError('Physical hash collision')
                    graph.archive[blob]=raw
                graph.roots|=branch.roots
                for version,targets in branch.targets.items():graph.targets[f'{dataset}-{model}-{seed}-{version}']=targets
                branches.append(dict(dataset=dataset,estimator=model,seed=seed,versions=versions,accuracy=info['accuracy']))
        families={'split':'membership','fit_scaler':'sklearn_preprocessing','scale_sklearn':'sklearn_preprocessing','scale':'numpy_scaling'}
        caps={nid:families[n.op] for nid,n in graph.nodes.items() if n.op in families and n.replayable}
        groups=sorted(set(caps.values()));plans=[]
        snapshot=graph.roots|{graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
        for k in (1,2):
            selected={};diagnostics={}
            for trial in range(3):
                order=[('robust',optimize),('expanded_exact',expanded)]
                if trial%2:order.reverse()
                for policy,solver in order:
                    stamp=time.time_ns();start=time.perf_counter();cpu=time.process_time()
                    store,status,diag=solver(graph,caps,k,time_limit_s=60.)
                    elapsed=time.perf_counter()-start;used=time.process_time()-cpu
                    if status!='ok' or not diag['storage_optimal']:raise RuntimeError('Mixed graph unproved optimum '+policy+' '+status)
                    selected[policy]=store;diagnostics[policy]=diag
                    planning.append(dict(k=k,trial=trial,policy=policy,elapsed_s=elapsed,cpu_s=used,
                        start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),diagnostic=diag))
                    print(json.dumps(dict(k=k,trial=trial,policy=policy,elapsed_s=elapsed)),flush=True)
            if retained_bytes(graph,selected['robust'],caps,k)!=retained_bytes(graph,selected['expanded_exact'],caps,k):raise RuntimeError('Mixed optima differ')
            for policy,retained in selected.items():
                store=destination/'stores'/f'k{k}'/policy;write_store(graph,retained,store)
                (store/'capability_contract.json').write_bytes(contract(caps,k))
                exact=0
                for count in range(k+1):
                    for lost in itertools.combinations(groups,count):
                        for version,targets in graph.targets.items():
                            disk=Graph.read(store/'manifest.json');restorer=CapabilityRestorer(disk,store,caps,lost)
                            stamp=time.time_ns();start=time.perf_counter();cpu=time.process_time();values=restorer.version(version)
                            if not all(pack(v)==graph.archive[graph.nodes[t].blob] for v,t in zip(values,targets)):raise RuntimeError('Mixed recovery differs')
                            if any(e.get('producer') and caps.get(e['producer']) in lost for e in restorer.trace):raise RuntimeError('Disabled producer executed')
                            exact+=1;traces.append(dict(k=k,policy=policy,version=version,disabled=list(lost),
                                start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),latency_s=time.perf_counter()-start,
                                cpu_s=time.process_time()-cpu,exact=True,capture_archive_absent=not disk.archive,events=restorer.trace))
                size=retained_bytes(graph,retained,caps,k);full=retained_bytes(graph,snapshot,caps,k)
                rows.append(dict(k=k,policy=policy,retained_bytes=size,snapshot_bytes=full,
                    saving_vs_snapshots=100*(1-size/full),exact=exact))
            plans.append(dict(k=k,selected={p:sorted(s) for p,s in selected.items()},diagnostics=diagnostics))
    for name,value in [('execution_traces',traces),('planning_trials',planning),('planner_certificates',plans)]:
        (destination/(name+'.json.gz')).write_bytes(gzip.compress((json.dumps(value,indent=2)+'\n').encode(),mtime=0))
    report=dict(branches=branches,histories=len(branches),protected_versions=len(graph.targets),
        logical_nodes=len(graph.nodes),physical_blobs=len(graph.candidates),mandatory_physical_blobs=len(graph.roots),
        shared_capability_groups=groups,rows=rows,exact_requests=len(traces),planner_runs=len(planning),
        source_sha256=digest(Path(__file__).read_bytes()),
        source_dependencies={n:digest(Path(__file__).with_name(n).read_bytes()) for n in
            ('witness_pipeline.py','capability_ops.py','capability_retention.py','scenario_retention.py','witness.py')},
        qualification='One merged graph of independently captured real-data branches; shared global replay loss groups; not 112 independent datasets')
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=run(a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('branches','source_dependencies')},indent=2))
