"""Fresh matched released HYPPO and published HELIX decision rule study."""
import argparse,csv,gzip,itertools,json,resource,time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,RestoreError,pack,digest,write_store,environment
from .witness_pipeline import capture
from .component_retention import optimize
from .capability_retention import retained_bytes,contract,CapabilityRestorer,restricted
from .published_materializers import load_source,select as hyppo,REVISION,SOURCE_SHA256
from .helix_materializer import select as helix
from .witness import certificate


def run(destination,hyppo_cache):
    destination.mkdir(parents=True,exist_ok=False);module=load_source(hyppo_cache)
    rows=[];traces=[];plans=[];quality=[]
    workloads=[(d,'logistic',fmt,3,12) for d in ('breast_cancer','iris','wine','banknote') for fmt in ('npy','csv6')]
    workloads += [('digits',m,'npy',2,4) for m in ('forest','mlp')]
    with threadpool_limits(limits=1):
        for dataset,model,fmt,seeds,versions in workloads:
            for seed in range(seeds):
                g,info=capture(dataset,seed,fmt,versions,dual_scalers=True,estimator=model)
                quality.append(dict(dataset=dataset,model=model,format=fmt,seed=seed,accuracy=info['accuracy']))
                families={'split':'membership','fit_scaler':'sklearn_preprocessing','scale_sklearn':'sklearn_preprocessing','scale':'numpy_scaling'}
                caps={nid:families[n.op] for nid,n in g.nodes.items() if n.op in families and n.replayable}
                groups=sorted(set(caps.values()));snapshots=g.roots|{g.nodes[t].blob for ts in g.targets.values() for t in ts}
                for k in (1,2):
                    case=f'{dataset}-{model}-{seed:02d}-{fmt}-k{k}'
                    robust,status,diag=optimize(g,caps,k,time_limit_s=60.)
                    if status!='ok' or not diag['robust_certified'] or not diag['storage_optimal']:raise RuntimeError('Uncertified '+case)
                    fixed=retained_bytes(g,g.roots,caps,k);budget=retained_bytes(g,robust,caps,k);optional=budget-fixed
                    full=retained_bytes(g,snapshots,caps,k)
                    policies={'RecoverML_decomposed':robust,'HYPPO_rank':hyppo(g,optional,module),'HYPPO_frequency':hyppo(g,optional,module,True)}
                    annotations={}
                    for speed in (50,200,800):
                        for reverse in (False,True):
                            name=f'HELIX_{speed}MiB_'+('reverse' if reverse else 'capture')
                            policies[name],annotations[name]=helix(g,optional,speed*1024**2,reverse)
                    policies['HELIX_snapshot_budget'],annotations['HELIX_snapshot_budget']=helix(g,full-fixed,200*1024**2)
                    plans.append(dict(case=case,robust=diag,capabilities=caps,helix_decisions=annotations,selected={p:sorted(s) for p,s in policies.items()}))
                    faults=[f for n in range(k+1) for f in itertools.combinations(groups,n)]
                    for policy,selected in policies.items():
                        store=destination/'stores'/case/policy;write_store(g,selected,store)
                        (store/'capability_contract.json').write_bytes(contract(caps,k));total=retained_bytes(g,selected,caps,k)
                        if total!=sum(p.stat().st_size for p in store.rglob('*') if p.is_file()):raise RuntimeError('Byte accounting')
                        if policy!='HELIX_snapshot_budget' and total>budget:raise RuntimeError('Common limit exceeded')
                        exact=blocked=attempts=0
                        for lost in faults:
                            disk=Graph.read(store/'manifest.json');coverage=certificate(restricted(disk,caps,lost),selected)['version_coverage']
                            for version,targets in g.targets.items():
                                r=CapabilityRestorer(disk,store,caps,lost);stamp=time.time_ns();clock=time.perf_counter();cpu=time.process_time();ok=False;error=None
                                try:
                                    values=r.version(version);ok=all(pack(v)==g.archive[g.nodes[t].blob] for v,t in zip(values,targets))
                                    if not ok:raise RuntimeError('Target bytes mismatch')
                                except RestoreError as exc:
                                    if coverage[version]:raise RuntimeError('Unexpected failure') from exc
                                    error=str(exc)
                                if any(e.get('producer') and caps.get(e['producer']) in lost for e in r.trace):raise RuntimeError('Disabled producer executed')
                                attempts+=1;exact+=int(ok);blocked+=int(error is not None)
                                traces.append(dict(case=case,policy=policy,version=version,disabled=list(lost),exact=ok,expected_blocked=error is not None,error=error,
                                    events=r.trace,start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),latency_s=time.perf_counter()-clock,cpu_s=time.process_time()-cpu,capture_archive_absent=not disk.archive))
                        if policy=='RecoverML_decomposed' and exact!=attempts:raise RuntimeError('Robust failure')
                        rows.append(dict(case=case,dataset=dataset,estimator=model,format=fmt,seed=seed,k=k,versions=versions,policy=policy,
                            retained_bytes=total,robust_budget=budget,snapshot_bytes=full,requests=attempts,exact=exact,blocked=blocked,within_robust_budget=total<=budget))
                    print(json.dumps(dict(completed_case=case,byte_optimum=budget)),flush=True)
    with (destination/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    for name,value in [('execution_traces',traces),('planner_certificates',plans)]:
        (destination/(name+'.json.gz')).write_bytes(gzip.compress((json.dumps(value,indent=2)+'\n').encode(),mtime=0))
    report=dict(planning_cases=len(plans),histories=len(quality),requests=len(traces),exact=sum(t['exact'] for t in traces),quality=quality,
        helix_scope='Published Algorithm 2 and Definition 6 reimplementation with logical capture order and physical payload adapter; not native HELIX',
        hyppo_scope='Pinned unchanged released materialization components; not full-system HYPPO',hyppo_revision=REVISION,hyppo_source_sha256=SOURCE_SHA256,
        predeclared_sensitivity=dict(read_MiB_s=[50,200,800],tie_orders=['capture','reverse']),
        source_sha256=digest(Path(__file__).read_bytes()),source_dependencies={n:digest(Path(__file__).with_name(n).read_bytes()) for n in
            ('helix_materializer.py','published_materializers.py','component_retention.py','robust_retention.py','scenario_retention.py','capability_retention.py','capability_ops.py','witness_pipeline.py','witness.py')},
        process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,environment=environment())
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--hyppo-cache',type=Path,required=True);a=p.parse_args()
    r=run(a.output,a.hyppo_cache);print(json.dumps({k:v for k,v in r.items() if k not in ('quality','environment')},indent=2))
