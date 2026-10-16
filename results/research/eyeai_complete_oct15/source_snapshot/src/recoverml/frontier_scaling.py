"""Scaling study for exact replayability-frontier MILP reductions."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import shutil
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import wilcoxon
from threadpoolctl import threadpool_limits

from .core import DiskRestorer, Graph, canonical, write_store
from .policies import select
from .workloads import build_history


POLICIES = ('recoverability_v2','recoverability_v3','recoverability_v4')


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_csv(path: Path, rows: list[dict]):
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def bootstrap_interval(values, seed=10102026):
    values=np.asarray(values,dtype=float)
    rng=np.random.default_rng(seed)
    samples=np.median(rng.choice(values,(10000,len(values)),replace=True),axis=1)
    return [float(np.percentile(samples,2.5)),float(np.percentile(samples,97.5))]


def run(config_path: Path, out: Path) -> dict:
    config=json.loads(config_path.read_text())
    required={'dataset','model','rows','versions','trees','model_depth',
              'frontier_depths','repeats','timing_trials','budget_positions'}
    if not required <= config.keys():
        raise ValueError('Frontier config is missing required fields')
    if min(config['frontier_depths']) < 0 or min(config['budget_positions']) <= 0:
        raise ValueError('Depths must be nonnegative and budget positions positive')
    if max(config['budget_positions']) >= 1 or config['repeats'] < 2 or config['timing_trials'] < 2:
        raise ValueError('Use positions below one and at least two repeats and trials')
    out.mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_bytes(canonical(config))
    started=utc()
    rows=[]; captures=[]; verification=[]; traces=[]
    work=out/'_work'
    work.mkdir()
    manifests=gzip.open(out/'capture_manifests.jsonl.gz','wt')
    with manifests, threadpool_limits(limits=1):
        for depth in config['frontier_depths']:
            for repeat in range(config['repeats']):
                case_id=f'depth{depth:03d}-rep{repeat}'
                settings=dict(dataset=config['dataset'],rows=config['rows'],
                    versions=config['versions'],model=config['model'],change='parameters',
                    boundary='opaque',trees=config['trees'],depth=config['model_depth'],
                    pre_boundary_depth=depth)
                graph,capture=build_history(settings,seed=500+repeat)
                manifest=graph.manifest()
                manifest_raw=canonical(manifest)
                manifests.write(json.dumps(dict(case_id=case_id,manifest=manifest),
                                           separators=(',',':'))+'\n')
                sizes=graph.sizes()
                target_blobs=graph.roots | {
                    graph.nodes[target].blob
                    for targets in graph.targets.values() for target in targets}
                required_bytes=graph.size(graph.roots)
                target_bytes=graph.metadata_bytes()+sum(sizes[b] for b in target_blobs)
                captures.append(dict(case_id=case_id,depth=depth,repeat=repeat,
                    nodes=len(graph.nodes),unique_blobs=len(graph.candidates),
                    required_bytes=required_bytes,target_snapshot_bytes=target_bytes,
                    full_bytes=graph.size(graph.candidates),capture_s=capture['capture_total_s'],
                    manifest_sha256=hashlib.sha256(manifest_raw).hexdigest()))
                for position in config['budget_positions']:
                    budget=int(required_bytes+position*(target_bytes-required_bytes))
                    verified={}
                    for policy in POLICIES:
                        selection=select(graph,policy,budget)
                        if selection.status != 'ok':
                            raise RuntimeError(f'{case_id} {position} {policy} was not feasible')
                        if not graph.coverage(selection.retained)[0]:
                            raise RuntimeError('Planner returned incomplete coverage')
                        verified[policy]=selection
                    objectives={p:graph.estimate(s.retained) for p,s in verified.items()}
                    if not all(math.isclose(objectives[p],objectives[POLICIES[0]],
                                            rel_tol=1e-8,abs_tol=1e-10) for p in POLICIES):
                        raise RuntimeError('Planner objective changed after frontier reduction')

                    # Execute V4 once per version while keeping this work out of
                    # the planning timing samples below.
                    store=work/f'{case_id}-{position}'
                    write_store(graph,verified['recoverability_v4'].retained,store)
                    replay_graph=Graph.read(store/'manifest.json')
                    for version in range(config['versions']):
                        restorer=DiskRestorer(replay_graph,store)
                        restorer.version(str(version))
                        verification.append(dict(case_id=case_id,depth=depth,repeat=repeat,
                            budget_position=position,version=version,exact=True,
                            operations=len(restorer.trace)))
                        traces.extend(dict(case_id=case_id,budget_position=position,
                                           version=version,**entry) for entry in restorer.trace)
                    shutil.rmtree(store)

                    for trial in range(config['timing_trials']):
                        offset=(depth+repeat+trial)%len(POLICIES)
                        order=POLICIES[offset:]+POLICIES[:offset]
                        measured={p:select(graph,p,budget) for p in order}
                        statuses={s.status for s in measured.values()}
                        costs={p:graph.estimate(s.retained) for p,s in measured.items()}
                        equivalent=(len(statuses)==1 and next(iter(statuses))=='ok' and
                            all(math.isclose(costs[p],costs[POLICIES[0]],
                                             rel_tol=1e-8,abs_tol=1e-10) for p in POLICIES))
                        proven_optimal=all(measured[p].history[0]['estimated_optimal']
                                           for p in POLICIES)
                        if proven_optimal and not equivalent:
                            raise RuntimeError('Proven-optimal frontier formulations disagree')
                        for order_index,policy in enumerate(order):
                            selection=measured[policy]
                            diag=selection.history[0]
                            rows.append(dict(case_id=case_id,depth=depth,repeat=repeat,
                                budget_position=position,budget_bytes=budget,trial=trial,
                                order_index=order_index,policy=policy,status=selection.status,
                                objective_s=costs[policy],objective_equivalent=equivalent,
                                all_planners_proven_optimal=proven_optimal,
                                planner_proven_optimal=diag['estimated_optimal'],
                                solver_status=diag['solver_status'],
                                planning_ms=selection.planning_s*1000,
                                solver_ms=diag['solver_s']*1000,variables=diag['variables'],
                                constraints=diag['constraints'],
                                physical_candidates=diag['physical_candidates'],
                                retained_bytes=graph.size(selection.retained)))
                print(f'{case_id}: {len(graph.nodes)} nodes and all checks passed',flush=True)
    shutil.rmtree(work)

    grouped=defaultdict(list)
    for row in rows:
        grouped[(row['case_id'],row['depth'],row['repeat'],
                 row['budget_position'],row['policy'])].append(row)
    medians=[]
    for key,group in sorted(grouped.items()):
        case_id,depth,repeat,position,policy=key
        medians.append(dict(case_id=case_id,depth=depth,repeat=repeat,
            budget_position=position,policy=policy,
            median_planning_ms=statistics.median(r['planning_ms'] for r in group),
            median_solver_ms=statistics.median(r['solver_ms'] for r in group),
            variables=group[0]['variables'],constraints=group[0]['constraints'],
            physical_candidates=group[0]['physical_candidates']))

    by_history=defaultdict(lambda:defaultdict(list))
    for row in medians:
        by_history[row['case_id']][row['policy']].append(row['median_planning_ms'])
    history=[]
    for case_id,policies in sorted(by_history.items()):
        values={p:statistics.median(policies[p]) for p in POLICIES}
        depth=next(r['depth'] for r in medians if r['case_id']==case_id)
        history.append(dict(case_id=case_id,depth=depth,
            v2_median_ms=values['recoverability_v2'],
            v3_median_ms=values['recoverability_v3'],
            v4_median_ms=values['recoverability_v4'],
            v2_to_v3_speedup=values['recoverability_v2']/values['recoverability_v3'],
            v2_to_v4_speedup=values['recoverability_v2']/values['recoverability_v4'],
            v3_to_v4_speedup=values['recoverability_v3']/values['recoverability_v4']))

    v2=[r['v2_median_ms'] for r in history]
    v4=[r['v4_median_ms'] for r in history]
    v2v4=[r['v2_to_v4_speedup'] for r in history]
    v3v4=[r['v3_to_v4_speedup'] for r in history]
    timing_sets=[r for r in rows if r['policy']=='recoverability_v2']
    paired=defaultdict(dict)
    for row in rows:
        paired[(row['case_id'],row['budget_position'],row['trial'])][row['policy']]=row
    deepest=max(config['frontier_depths'])
    deep_rows=[r for r in medians if r['depth']==deepest]
    deep_vars={p:int(statistics.median(r['variables'] for r in deep_rows if r['policy']==p))
               for p in POLICIES}
    report=dict(started_utc=started,ended_utc=utc(),dataset=config['dataset'],
        captured_histories=len(captures),timing_rows=len(rows),
        independent_history_summaries=len(history),
        exact_verified_restores=len(verification),
        timed_planner_sets=len(timing_sets),
        timed_objective_equivalent_sets=sum(r['objective_equivalent'] for r in timing_sets),
        all_proven_optimal_sets=sum(r['all_planners_proven_optimal'] for r in timing_sets),
        all_proven_optimal_sets_equivalent=all(r['objective_equivalent'] for r in timing_sets
                                               if r['all_planners_proven_optimal']),
        v2_proven_optimal_runs=sum(r['planner_proven_optimal'] for r in rows
                                   if r['policy']=='recoverability_v2'),
        v3_proven_optimal_runs=sum(r['planner_proven_optimal'] for r in rows
                                   if r['policy']=='recoverability_v3'),
        v4_proven_optimal_runs=sum(r['planner_proven_optimal'] for r in rows
                                   if r['policy']=='recoverability_v4'),
        v4_strictly_better_objective_sets=sum(
            group['recoverability_v4']['objective_s'] < group['recoverability_v2']['objective_s']-1e-10
            for group in paired.values()),
        median_v2_to_v4_speedup=float(np.median(v2v4)),
        median_v2_to_v4_speedup_bootstrap_95pct=bootstrap_interval(v2v4),
        v4_faster_than_v2_histories=sum(a>b for a,b in zip(v2,v4)),
        v2_vs_v4_wilcoxon_one_sided_p=float(wilcoxon(v2,v4,alternative='greater').pvalue),
        median_v3_to_v4_speedup=float(np.median(v3v4)),
        deepest_frontier_depth=deepest,deepest_variables=deep_vars,
        deepest_v2_to_v4_variable_reduction=(deep_vars['recoverability_v2']-
            deep_vars['recoverability_v4'])/deep_vars['recoverability_v2'],
        qualification='Local warm-cache study with a 0.5 second solver limit; proven optima and exact restores are checked')

    write_csv(out/'raw_planner_trials.csv',rows)
    write_csv(out/'setting_medians.csv',medians)
    write_csv(out/'history_medians.csv',history)
    write_csv(out/'capture_metrics.csv',captures)
    write_csv(out/'restore_verification.csv',verification)
    with (out/'execution_traces.jsonl').open('w') as handle:
        for row in traces:
            handle.write(json.dumps(row,separators=(',',':'))+'\n')
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'environment.json').write_bytes(canonical(graph.env))

    fig,ax=plt.subplots(figsize=(7.2,5.2),constrained_layout=True)
    labels={'recoverability_v2':'V2 full model','recoverability_v3':'V3 frontier',
            'recoverability_v4':'V4 compact frontier'}
    for policy in POLICIES:
        xs=[]; ys=[]; lower=[]; upper=[]
        for depth in config['frontier_depths']:
            values=[r['median_planning_ms'] for r in medians
                    if r['policy']==policy and r['depth']==depth]
            xs.append(depth); ys.append(float(np.median(values)))
            lower.append(float(np.percentile(values,25))); upper.append(float(np.percentile(values,75)))
        ax.plot(xs,ys,marker='o',label=labels[policy])
        ax.fill_between(xs,lower,upper,alpha=.13)
    ax.set(xlabel='Replayable operations before opaque frontier',
           ylabel='Median planning time (ms) · log scale',yscale='log',
           title='Replayability-frontier planning scales independently of hidden ancestry')
    ax.grid(alpha=.25); ax.legend()
    fig.savefig(out/'frontier_planning_scaling.png',dpi=180); plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.2,5.2),constrained_layout=True)
    for policy in POLICIES:
        values=[]
        for depth in config['frontier_depths']:
            values.append(statistics.median(r['variables'] for r in medians
                          if r['policy']==policy and r['depth']==depth))
        ax.plot(config['frontier_depths'],values,marker='o',label=labels[policy])
    ax.set(xlabel='Replayable operations before opaque frontier',ylabel='MILP binary variables',
           title='Exact frontier reduction removes irrelevant decision variables')
    ax.grid(alpha=.25); ax.legend()
    fig.savefig(out/'frontier_variable_scaling.png',dpi=180); plt.close(fig)

    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.iterdir()) if p.is_file()}
    (out/'HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
    (out/'RUN_COMPLETE').write_text('All planner pairs and exact restores completed.\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.config,args.out),indent=2))
