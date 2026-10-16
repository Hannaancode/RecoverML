"""Exact retention control with training and prediction replay call losses."""
import argparse,csv,gzip,itertools,json,time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,pack,digest,write_store
from .witness_pipeline import capture
from .component_retention import optimize
from .scenario_retention import optimize as expanded
from .capability_retention import retained_bytes,contract,CapabilityRestorer

def run(destination):
    destination.mkdir(parents=True,exist_ok=False);rows=[];plans=[];traces=[]
    with threadpool_limits(limits=1):
        for dataset,model,versions in [('banknote','logistic',12),('digits','forest',4),('digits','mlp',4)]:
            for seed in (0,1):
                g,_=capture(dataset,seed,'npy',versions,dual_scalers=True,estimator=model)
                feature={'split':'membership','fit_scaler':'sklearn_preprocessing','scale_sklearn':'sklearn_preprocessing','scale':'numpy_scaling'}
                for scope in ('feature_only','with_training','with_training_prediction'):
                    mapping=dict(feature)
                    if scope!='feature_only':mapping.update(train='training',train_mlp='training')
                    if scope=='with_training_prediction':mapping['predict']='prediction'
                    caps={nid:mapping[n.op] for nid,n in g.nodes.items() if n.op in mapping and n.replayable};groups=sorted(set(caps.values()))
                    snapshot=g.roots|{g.nodes[t].blob for ts in g.targets.values() for t in ts}
                    for k in (1,2):
                        case=f'{model}-{seed}-{scope}-k{k}';selections={};diags={}
                        for name,solver in [('decomposed',optimize),('expanded_exact',expanded)]:
                            selected,status,diag=solver(g,caps,k,time_limit_s=60.)
                            if status!='ok' or not diag['storage_optimal']:raise RuntimeError('Uncertified broad fault scope')
                            selections[name]=selected;diags[name]=diag
                        sizes={p:retained_bytes(g,s,caps,k) for p,s in selections.items()}
                        if len(set(sizes.values()))!=1:raise RuntimeError('Broad fault optima disagree')
                        plans.append(dict(case=case,scope=scope,k=k,capabilities=caps,diagnostics=diags,selected={p:sorted(s) for p,s in selections.items()}))
                        for policy,selected in selections.items():
                            store=destination/'stores'/case/policy;write_store(g,selected,store);(store/'capability_contract.json').write_bytes(contract(caps,k));exact=0
                            for count in range(k+1):
                                for lost in itertools.combinations(groups,count):
                                    for version,targets in g.targets.items():
                                        disk=Graph.read(store/'manifest.json');r=CapabilityRestorer(disk,store,caps,lost)
                                        stamp=time.time_ns();clock=time.perf_counter();cpu=time.process_time();values=r.version(version)
                                        if not all(pack(v)==g.archive[g.nodes[t].blob] for v,t in zip(values,targets)):raise RuntimeError('Broad fault target mismatch')
                                        if any(e.get('producer') and caps.get(e['producer']) in lost for e in r.trace):raise RuntimeError('Disabled broad fault producer used')
                                        exact+=1;traces.append(dict(case=case,policy=policy,version=version,disabled=list(lost),exact=True,
                                            capture_archive_absent=not disk.archive,start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),
                                            latency_s=time.perf_counter()-clock,cpu_s=time.process_time()-cpu,events=r.trace))
                            full=retained_bytes(g,snapshot,caps,k)
                            rows.append(dict(case=case,estimator=model,seed=seed,scope=scope,groups=len(groups),k=k,policy=policy,
                                retained_bytes=sizes[policy],snapshot_bytes=full,saving_vs_snapshots=100*(1-sizes[policy]/full),exact_requests=exact))
                        print(json.dumps(dict(completed_case=case,minimum=sizes['decomposed'])),flush=True)
    with (destination/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    for name,value in [('execution_traces',traces),('planner_certificates',plans)]:
        (destination/(name+'.json.gz')).write_bytes(gzip.compress((json.dumps(value,indent=2)+'\n').encode(),mtime=0))
    report=dict(histories=6,scope_cases=len(plans),exact_requests=len(traces),all_byte_optima_match=True,
        source_sha256=digest(Path(__file__).read_bytes()),source_dependencies={n:digest(Path(__file__).with_name(n).read_bytes()) for n in
            ('witness_pipeline.py','capability_ops.py','component_retention.py','robust_retention.py','scenario_retention.py','capability_retention.py','witness.py')},
        qualification='Injected replay call restrictions including fitting and prediction with intact files and matching numerical environment')
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.output),indent=2))
