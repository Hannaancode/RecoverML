"""Paired negative and partial-frontier controls, not cherry-picked opaque DAGs."""
import argparse
import csv
import hashlib
import json
import math
import statistics
import time
from datetime import datetime,timezone
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from threadpoolctl import threadpool_limits
from .core import Graph,DiskRestorer,canonical,write_store
from .optimizer import optimize
from .topology_scaling import build_wide_history
from .benchmark import write_csv


def bootstrap(values):
    rng=np.random.default_rng(913)
    x=np.asarray(values,dtype=float)
    estimates=np.median(rng.choice(x,size=(10000,len(x)),replace=True),axis=1)
    return np.percentile(estimates,[2.5,97.5]).tolist()


def run(config_path,out):
    config=json.loads(config_path.read_text());out.mkdir(parents=True,exist_ok=False)
    rows=[];restores=[];traces=[];captures=[];groups=[]
    with threadpool_limits(limits=1):
        for mode in ('none','mixed','all'):
            for width in config['widths']:
                for repeat in range(config['repeats']):
                    case=f'{mode}-w{width:03d}-r{repeat}'
                    g=build_wide_history(width,config['depth'],config['versions'],18000+repeat,mode)
                    target=g.roots|{g.nodes[t].blob for ts in g.targets.values() for t in ts}
                    budget=g.size(target)
                    captures.append(dict(case_id=case,mode=mode,width=width,repeat=repeat,
                        nodes=len(g.nodes),edges=sum(len(n.deps) for n in g.nodes.values()),
                        budget_bytes=budget,full_bytes=g.size(g.candidates)))
                    results={}
                    for trial in range(config['trials']):
                        order=['v2','v3','v4'];order=order[trial%3:]+order[:trial%3]
                        objectives=[]
                        for oi,policy in enumerate(order):
                            began=time.perf_counter();cpu=time.process_time();stamp=datetime.now(timezone.utc).isoformat()
                            kept,status,h=optimize(g,budget,time_limit_s=5.,prune_opaque=policy!='v2',compact=policy=='v4')
                            wall=time.perf_counter()-began;cpu=time.process_time()-cpu
                            if status!='ok' or not h[0]['estimated_optimal']:
                                raise RuntimeError(f'Planner was not optimal: {case} {policy} {status}')
                            objective=g.estimate(kept);objectives.append(objective)
                            rows.append(dict(case_id=case,mode=mode,width=width,repeat=repeat,
                                trial=trial,policy=policy,order_index=oi,utc=stamp,
                                wall_ms=wall*1000,cpu_ms=cpu*1000,
                                variables=h[0].get('variables',0),constraints=h[0].get('constraints',0),
                                objective_s=objective,proven_optimal=h[0]['estimated_optimal']))
                            results[policy]=kept
                        if not all(math.isclose(o,objectives[0],rel_tol=1e-8,abs_tol=1e-10) for o in objectives):
                            raise RuntimeError('Paired objective disagreement')
                    import tempfile
                    with tempfile.TemporaryDirectory() as temporary:
                        store=Path(temporary)/'store';write_store(g,results['v4'],store)
                        rg=Graph.read(store/'manifest.json')
                        for version in g.targets:
                            engine=DiskRestorer(rg,store);engine.version(version)
                            restores.append(dict(case_id=case,mode=mode,version=version,exact=True))
                            traces.extend(dict(case_id=case,version=version,**event) for event in engine.trace)
                    med={p:statistics.median(r['wall_ms'] for r in rows if r['case_id']==case and r['policy']==p) for p in ('v2','v3','v4')}
                    variables={p:next(r['variables'] for r in rows if r['case_id']==case and r['policy']==p) for p in med}
                    groups.append(dict(case_id=case,mode=mode,width=width,repeat=repeat,
                        v2_ms=med['v2'],v3_ms=med['v3'],v4_ms=med['v4'],
                        speedup_v2_v4=med['v2']/med['v4'],
                        v2_variables=variables['v2'],v3_variables=variables['v3'],v4_variables=variables['v4']))
                    print(f'{case}: optimum and exact restore passed',flush=True)
    summary={}
    for mode in ('none','mixed','all'):
        cases=[g for g in groups if g['mode']==mode]
        values=[g['speedup_v2_v4'] for g in cases]
        summary[mode]=dict(histories=len(cases),median_speedup=float(np.median(values)),
            bootstrap_95_ci=bootstrap(values),v4_faster_histories=sum(v>1 for v in values),
            v3_equals_v2_variables=all(g['v3_variables']==g['v2_variables'] for g in cases),
            median_variable_reduction=float(np.median([1-g['v4_variables']/g['v2_variables'] for g in cases])))
    report=dict(histories=len(captures),planner_executions=len(rows),exact_restores=len(restores),
        all_objectives_equivalent=True,all_proven_optimal=True,by_mode=summary,
        qualification='Executable controlled topology; zero replay costs deliberately force the global model; history-level bootstrap on one machine')
    write_csv(out/'planner_trials.csv',rows);write_csv(out/'history_medians.csv',groups)
    write_csv(out/'capture_metrics.csv',captures);write_csv(out/'restore_verification.csv',restores)
    (out/'config.json').write_bytes(canonical(config));(out/'summary.json').write_bytes(canonical(report))
    (out/'environment.json').write_bytes(canonical(g.env))
    with (out/'execution_traces.jsonl').open('w') as h:
        for event in traces:h.write(json.dumps(event)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for mode in ('none','mixed','all'):
        cases=[g for g in groups if g['mode']==mode]
        axes[0].scatter([g['width'] for g in cases],[g['speedup_v2_v4'] for g in cases],label=mode,alpha=.6)
        axes[1].scatter([g['width'] for g in cases],[100*(1-g['v4_variables']/g['v2_variables']) for g in cases],label=mode,alpha=.6)
    axes[0].axhline(1,color='black',linestyle='--');axes[0].set(xlabel='Branch width',ylabel='V2 / V4 planning time',yscale='log')
    axes[1].set(xlabel='Branch width',ylabel='V4 variable reduction (%)');axes[0].legend(title='Boundary placement')
    fig.savefig(out/'boundary_controls.png',dpi=180);plt.close(fig)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out/'HASHES.json').write_bytes(canonical(hashes));return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(run(args.config,args.out),indent=2))

if __name__=='__main__':main()
