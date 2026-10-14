"""Real-data replay-capability outage injection and robust storage evaluation.

The bounded fault model disables split, scaler fitting and feature scaling
replay capabilities. Training/prediction and file decoding remain available.
These are declared capability outages, not removal of installed packages.
All current results stay intact; this produces new stores and raw request logs.
"""
import argparse
import csv
import itertools
import json
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,RestoreError,digest,pack,write_store
from .witness_pipeline import capture
from .witness_optimizer import optimize as nominal
from .capability_retention import optimize,contract,retained_bytes,CapabilityRestorer,restricted
from .witness import certificate


def run(destination,seeds=2,versions=12,datasets=('breast_cancer','iris','wine')):
    destination.mkdir(parents=True,exist_ok=False)
    rows,traces,plans,provenance=[],[],[],[]
    with threadpool_limits(limits=1):
        for name in datasets:
            for seed in range(seeds):
                for transport in ('npy','csv6'):
                    graph,info=capture(name,seed,transport,versions)
                    caps={nid:n.op for nid,n in graph.nodes.items() if n.replayable and
                          n.op in ('split','fit_scaler','scale')}
                    groups=sorted(set(caps.values()))
                    protected=graph.roots|{graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
                    selected,status,diag=nominal(graph)
                    if status!='ok' or not diag['storage_optimal']: raise RuntimeError('Unproved nominal plan')
                    for k in (1,2):
                        case=f'{name}-{seed:02d}-{transport}-k{k}'
                        robust,robust_status,robust_diag=optimize(graph,caps,k,time_limit_s=30.,max_iterations=1000)
                        if robust_status!='ok' or not robust_diag['robust_certified'] or not robust_diag['storage_optimal']:
                            raise RuntimeError(f'Unproved robust plan {case} {robust_status}')
                        faults=[tuple(f) for count in range(k+1) for f in itertools.combinations(groups,count)]
                        strategies={'nominal':selected,'robust':robust,'snapshots':protected}
                        outcome={p:dict(attempts=0,exact=0,blocked=0) for p in strategies}
                        for policy,retained in strategies.items():
                            store=destination/'stores'/case/policy
                            write_store(graph,retained,store)
                            (store/'capability_contract.json').write_bytes(contract(caps,k))
                            actual=sum(p.stat().st_size for p in store.rglob('*') if p.is_file())
                            if actual!=retained_bytes(graph,retained,caps,k): raise RuntimeError('Stored-byte accounting mismatch')
                            disk=Graph.read(store/'manifest.json')
                            for lost in faults:
                                view=restricted(disk,caps,lost)
                                coverage=certificate(view,retained)['version_coverage']
                                for version,targets in graph.targets.items():
                                    restorer=CapabilityRestorer(disk,store,caps,lost)
                                    start=time.time_ns();cpu=time.process_time();error=None;exact=False
                                    outcome[policy]['attempts']+=1
                                    try:
                                        values=restorer.version(version)
                                        exact=all(pack(value)==graph.archive[graph.nodes[t].blob] for t,value in zip(targets,values))
                                        if not exact: raise RuntimeError('Capability recovery mismatch')
                                        outcome[policy]['exact']+=1
                                    except RestoreError as exc:
                                        if policy!='nominal' or coverage[version]:
                                            raise RuntimeError('Unexpected capability recovery failure') from exc
                                        outcome[policy]['blocked']+=1;error=str(exc)
                                    for event in restorer.trace:
                                        producer=event.get('producer')
                                        if producer and caps.get(producer) in lost:
                                            raise RuntimeError('Disabled replay producer executed')
                                    traces.append(dict(case=case,policy=policy,version=version,disabled=list(lost),
                                        start_timestamp_ns=start,end_timestamp_ns=time.time_ns(),cpu_s=time.process_time()-cpu,
                                        exact=exact,expected_blocked=error is not None,error=error,events=restorer.trace,
                                        capture_archive_absent=not disk.archive))
                        sizes={p:retained_bytes(graph,s,caps,k) for p,s in strategies.items()}
                        rows.append(dict(case=case,dataset=name,seed=seed,transport=transport,versions=versions,k=k,
                            fault_scenarios=len(faults),observed_feature_witness=info['observed_exact_feature_witness'],
                            nominal_bytes=sizes['nominal'],robust_bytes=sizes['robust'],snapshot_bytes=sizes['snapshots'],
                            robust_saving_vs_snapshots=100*(sizes['snapshots']-sizes['robust'])/sizes['snapshots'],
                            nominal_attempts=outcome['nominal']['attempts'],nominal_exact=outcome['nominal']['exact'],
                            robust_attempts=outcome['robust']['attempts'],robust_exact=outcome['robust']['exact'],
                            snapshot_exact=outcome['snapshots']['exact'],storage_cuts=robust_diag['cuts'],
                            robust_optimal=robust_diag['storage_optimal']))
                        plans.append(dict(case=case,capabilities=caps,robust_plan=robust_diag,
                                          retained={p:sorted(s) for p,s in strategies.items()}))
                        provenance.append(dict(case=case,**info,manifest_sha256=digest((destination/'stores'/case/'robust'/'manifest.json').read_bytes())))
    with (destination/'summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (destination/'execution_traces.json').write_text(json.dumps(traces,indent=2)+'\n')
    (destination/'planner_certificates.json').write_text(json.dumps(plans,indent=2)+'\n')
    (destination/'provenance.json').write_text(json.dumps(dict(cases=provenance,
        source_sha256=digest(Path(__file__).read_bytes()),
        planner_sha256=digest(Path(__file__).with_name('capability_retention.py').read_bytes()),
        pipeline_sha256=digest(Path(__file__).with_name('witness_pipeline.py').read_bytes()),
        qualification='Injected replay capability outages in constructed real-data histories; intact files and matching numerical environment required'),indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4))
    policies=['nominal','robust','snapshots']
    attempts=sum(r['nominal_attempts'] for r in rows)
    coverage=[100*sum(r[p+'_exact' if p!='snapshots' else 'snapshot_exact'] for r in rows)/attempts for p in policies]
    ax.bar(policies,coverage);ax.set_ylim(0,105);ax.set_ylabel('Exact recovery across allowed outages (%)')
    ax.set_title('Declared preprocessing capability-loss scenarios')
    fig.tight_layout();fig.savefig(destination/'outage_coverage.png',dpi=180);plt.close(fig)
    report=dict(cases=len(rows),attempts=len(traces),exact_requests=sum(r['exact'] for r in traces),
        expected_blocked=sum(r['expected_blocked'] for r in traces),
        robust_attempts=sum(r['robust_attempts'] for r in rows),robust_exact=sum(r['robust_exact'] for r in rows),
        snapshot_attempts=sum(r['nominal_attempts'] for r in rows),snapshot_exact=sum(r['snapshot_exact'] for r in rows),
        nominal_attempts=attempts,nominal_exact=sum(r['nominal_exact'] for r in rows))
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,default=2);parser.add_argument('--versions',type=int,default=12)
    parser.add_argument('--datasets',nargs='+',choices=['breast_cancer','iris','wine','banknote'],default=['breast_cancer','iris','wine'])
    args=parser.parse_args()
    if args.seeds<1 or args.versions<1: parser.error('Positive seeds and versions required')
    print(json.dumps(run(args.output,args.seeds,args.versions,tuple(args.datasets)),indent=2))
