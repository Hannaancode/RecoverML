"""Wide-DAG scaling study for the exact replayability-frontier reduction."""
import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from threadpoolctl import threadpool_limits

from .core import DiskRestorer, Graph, canonical, write_store
from .operators import execute
from .policies import select

POLICIES=('recoverability_v2','recoverability_v3','recoverability_v4')


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_csv(path, rows):
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def build_wide_history(width, depth, versions, seed, boundary_mode='all'):
    """Build a real executable DAG whose wide ancestry stops at opaque outputs."""
    if width < 1 or depth < 1 or versions < 1:
        raise ValueError('width depth and versions must be positive')
    if boundary_mode not in ('all','mixed','none'):
        raise ValueError('Unknown boundary mode')
    g=Graph(); values={}; rng=np.random.default_rng(seed)
    def add(op,deps,params,value=None,replayable=True,mandatory=False,version=0):
        if value is None:
            value=execute(op,[values[d] for d in deps],params)
        nid=g.add(op,deps,params,value,replayable,'topology-scaling',
                  0.0 if replayable else 1e-4,version,mandatory)
        values[nid]=value
        return nid
    root=add('input',[],{'kind':'wide-root'},
             np.ascontiguousarray(rng.normal(size=(8,8))),False,True)
    ends=[]
    for branch in range(width):
        node=root
        for layer in range(depth):
            node=add('affine_features',[node],
                     {'scale':1.0+(branch+1)*1e-6,
                      'offset':(layer+1)*(branch+1)*1e-7})
        if boundary_mode=='mixed' and branch%2==0:
            opaque=np.ascontiguousarray(values[node]+rng.normal(0,.001,values[node].shape))
            node=add('external_features',[node],{'branch':branch},opaque,False)
        ends.append(node)
    merged=add('mean_features',ends,{})
    for version in range(versions):
        if boundary_mode=='all':
            captured=np.ascontiguousarray(values[merged]+rng.normal(0,.001,values[merged].shape))
            node=add('external_features',[merged],{'version':version},captured,False,False,version)
        else:
            node=merged
        for layer in range(3):
            node=add('affine_features',[node],
                     {'scale':1.0+(version+1)*1e-5,
                      'offset':(layer+1)*1e-6},version=version)
        g.targets[str(version)]=[node]
    return g


def run(config_path, out):
    config=json.loads(config_path.read_text())
    out.mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_bytes(canonical(config))
    rows=[]; captures=[]; restores=[]; traces=[]; started=utc(); work=out/'_work'; work.mkdir()
    with threadpool_limits(limits=1):
        for topology in config['topologies']:
            width=int(topology['width']); depth=int(topology['depth'])
            for repeat in range(config['repeats']):
                case=f'w{width:03d}-d{depth:03d}-r{repeat}'
                g=build_wide_history(width,depth,config['versions'],9000+repeat)
                target_blobs=g.roots|{g.nodes[t].blob for ts in g.targets.values() for t in ts}
                budget=g.metadata_bytes()+sum(g.sizes()[b] for b in target_blobs)
                captures.append(dict(case_id=case,width=width,depth=depth,
                    versions=config['versions'],nodes=len(g.nodes),edges=sum(len(n.deps) for n in g.nodes.values()),
                    unique_blobs=len(g.candidates),full_bytes=g.size(g.candidates),budget_bytes=budget))
                first={p:select(g,p,budget) for p in POLICIES}
                if any(s.status!='ok' for s in first.values()):
                    raise RuntimeError(f'{case}: planner failed')
                objectives={p:g.estimate(s.retained) for p,s in first.items()}
                if not all(math.isclose(objectives[p],objectives[POLICIES[0]],rel_tol=1e-8,abs_tol=1e-10)
                           for p in POLICIES):
                    raise RuntimeError(f'{case}: objective mismatch')
                store=work/case
                write_store(g,first['recoverability_v4'].retained,store)
                rg=Graph.read(store/'manifest.json')
                for version in g.targets:
                    restorer=DiskRestorer(rg,store); restorer.version(version)
                    restores.append(dict(case_id=case,width=width,depth=depth,version=version,
                                         exact=True,operations=len(restorer.trace)))
                    traces.extend(dict(case_id=case,version=version,**t) for t in restorer.trace)
                shutil.rmtree(store)
                for trial in range(config['timing_trials']):
                    order=POLICIES[trial%3:]+POLICIES[:trial%3]
                    measured={p:select(g,p,budget) for p in order}
                    costs={p:g.estimate(measured[p].retained) for p in POLICIES}
                    equivalent=all(math.isclose(costs[p],costs[POLICIES[0]],rel_tol=1e-8,abs_tol=1e-10)
                                   for p in POLICIES)
                    for order_index,p in enumerate(order):
                        d=measured[p].history[0]
                        rows.append(dict(case_id=case,width=width,depth=depth,repeat=repeat,
                            trial=trial,order_index=order_index,policy=p,status=measured[p].status,
                            objective_s=costs[p],objective_equivalent=equivalent,
                            proven_optimal=d['estimated_optimal'],planning_ms=measured[p].planning_s*1000,
                            solver_ms=d.get('solver_s',0)*1000,variables=d.get('variables',0),
                            constraints=d.get('constraints',0),retained_bytes=g.size(measured[p].retained)))
                print(f'{case}: {len(g.nodes)} nodes passed',flush=True)
    shutil.rmtree(work)
    medians=[]
    for case in sorted({r['case_id'] for r in rows}):
        for policy in POLICIES:
            group=[r for r in rows if r['case_id']==case and r['policy']==policy]
            medians.append(dict(case_id=case,width=group[0]['width'],depth=group[0]['depth'],policy=policy,
                median_planning_ms=statistics.median(r['planning_ms'] for r in group),
                variables=group[0]['variables'],constraints=group[0]['constraints']))
    cases=sorted({r['case_id'] for r in rows})
    speedups=[]; reductions=[]
    for case in cases:
        m={r['policy']:r for r in medians if r['case_id']==case}
        speedups.append(m['recoverability_v2']['median_planning_ms']/m['recoverability_v4']['median_planning_ms'])
        reductions.append(1-m['recoverability_v4']['variables']/m['recoverability_v2']['variables'])
    report=dict(started_utc=started,ended_utc=utc(),histories=len(captures),
        planner_executions=len(rows),exact_restores=len(restores),max_nodes=max(r['nodes'] for r in captures),
        max_edges=max(r['edges'] for r in captures),all_objectives_equivalent=all(r['objective_equivalent'] for r in rows),
        all_solver_runs_proven_optimal=all(r['proven_optimal'] for r in rows),
        median_v2_to_v4_speedup=float(np.median(speedups)),
        median_variable_reduction=float(np.median(reductions)),
        largest_case_variable_reduction=float(reductions[max(range(len(cases)),key=lambda i:captures[i]['nodes'])]),
        qualification='Executable synthetic topology study; values are small arrays and results measure planner scaling not neural training')
    write_csv(out/'raw_planner_trials.csv',rows); write_csv(out/'case_medians.csv',medians)
    write_csv(out/'capture_metrics.csv',captures); write_csv(out/'restore_verification.csv',restores)
    with (out/'execution_traces.jsonl').open('w') as h:
        for row in traces: h.write(json.dumps(row,separators=(',',':'))+'\n')
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'environment.json').write_bytes(canonical(g.env))
    fig,ax=plt.subplots(figsize=(7.2,5.2),constrained_layout=True)
    labels={'recoverability_v2':'V2 full model','recoverability_v3':'V3 frontier','recoverability_v4':'V4 compact frontier'}
    for policy in POLICIES:
        group=sorted((r for r in medians if r['policy']==policy),key=lambda r:(r['width']*r['depth'],r['case_id']))
        ax.plot([r['width']*r['depth'] for r in group],[r['median_planning_ms'] for r in group],marker='o',label=labels[policy])
    ax.set(xlabel='Replayable nodes hidden behind boundary',ylabel='Median planning time (ms) · log scale',yscale='log',
           title='Wide-DAG replayability-frontier scaling'); ax.grid(alpha=.25); ax.legend()
    fig.savefig(out/'topology_planning_scaling.png',dpi=180); plt.close(fig)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
    (out/'RUN_COMPLETE').write_text('All wide-topology histories planners and exact restores completed.\n')
    return report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); print(json.dumps(run(args.config,args.out),indent=2))


if __name__=='__main__':
    main()
