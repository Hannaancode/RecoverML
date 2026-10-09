"""Repeated paired timing study for opaque-boundary planner pruning."""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import wilcoxon
from threadpoolctl import threadpool_limits

from .core import Graph
from .policies import select


def write_csv(path: Path, rows: list[dict]):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(source: Path, out: Path, trials: int = 30) -> dict:
    if trials < 2:
        raise ValueError('At least two timing trials are required')
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads((source/'config.json').read_text())
    plans = [json.loads(line) for line in (source/'retention_plans.jsonl').open()]
    case_settings = {
        f'case{case_index:02d}-rep{repeat}': dict(case, repeat=repeat)
        for case_index,case in enumerate(config['cases'])
        for repeat in range(config['repeats'])
    }
    eligible = []
    for plan in plans:
        history = plan['eviction_trace'][0] if plan['eviction_trace'] else {}
        if (plan['policy'] == 'recoverability_v2' and
                case_settings[plan['case_id']]['boundary'] == 'opaque' and
                history.get('strategy') == 'bounded_global_milp'):
            eligible.append(plan)
    if not eligible:
        raise ValueError('No opaque bounded-MILP selections were found')

    rows = []
    with threadpool_limits(limits=1):
        for selection_index,plan in enumerate(eligible):
            case_id = plan['case_id']
            settings = case_settings[case_id]
            graph = Graph.read(source/'capture_archives'/case_id/'manifest.json')
            for trial in range(trials):
                order = ['recoverability_v2','recoverability_v3']
                if (selection_index + trial) % 2:
                    order.reverse()
                results = {}
                for policy in order:
                    results[policy] = select(graph,policy,plan['budget_bytes'])
                v2,v3 = results['recoverability_v2'],results['recoverability_v3']
                same = v2.status == v3.status and v2.retained == v3.retained
                if not same:
                    raise RuntimeError('V3 changed the V2 decision')
                d2,d3 = v2.history[0],v3.history[0]
                rows.append(dict(case_id=case_id,dataset=settings['dataset'],model=settings['model'],
                    repeat=settings['repeat'],budget_fraction=plan['budget_fraction'],trial=trial,
                    first_policy=order[0],status=v2.status,retained_identical=same,
                    v2_planning_ms=v2.planning_s*1000,v3_planning_ms=v3.planning_s*1000,
                    v2_solver_ms=d2['solver_s']*1000,v3_solver_ms=d3['solver_s']*1000,
                    v2_variables=d2['variables'],v3_variables=d3['variables'],
                    v2_physical_candidates=d2['physical_candidates'],
                    v3_physical_candidates=d3['physical_candidates']))

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['case_id'],row['budget_fraction'])].append(row)
    selections = []
    for (case_id,budget),group in sorted(grouped.items()):
        v2 = statistics.median(r['v2_planning_ms'] for r in group)
        v3 = statistics.median(r['v3_planning_ms'] for r in group)
        selections.append(dict(case_id=case_id,budget_fraction=budget,
            v2_median_ms=v2,v3_median_ms=v3,speedup=v2/v3))

    by_history = defaultdict(list)
    for row in selections:
        by_history[row['case_id']].append(row)
    histories = []
    for case_id,group in sorted(by_history.items()):
        v2 = statistics.median(r['v2_median_ms'] for r in group)
        v3 = statistics.median(r['v3_median_ms'] for r in group)
        histories.append(dict(case_id=case_id,v2_median_ms=v2,
            v3_median_ms=v3,speedup=v2/v3))

    test = wilcoxon([r['v2_median_ms'] for r in histories],
                    [r['v3_median_ms'] for r in histories],alternative='greater')
    speedups = np.asarray([r['speedup'] for r in histories])
    rng = np.random.default_rng(9102026)
    bootstrap = np.median(rng.choice(speedups,(10000,len(speedups)),replace=True),axis=1)
    v2_variables = statistics.median(r['v2_variables'] for r in rows)
    v3_variables = statistics.median(r['v3_variables'] for r in rows)
    report = dict(source=str(source),timing_trials=len(rows),trials_per_selection=trials,
        opaque_solver_selections=len(selections),opaque_histories=len(histories),
        identical_decisions=sum(r['retained_identical'] for r in rows),
        v2_median_planning_ms=statistics.median(r['v2_planning_ms'] for r in rows),
        v3_median_planning_ms=statistics.median(r['v3_planning_ms'] for r in rows),
        median_history_speedup=float(np.median(speedups)),
        median_history_speedup_bootstrap_95pct=[float(np.percentile(bootstrap,2.5)),
                                                float(np.percentile(bootstrap,97.5))],
        v3_faster_histories=sum(r['v3_median_ms'] < r['v2_median_ms'] for r in histories),
        wilcoxon_history_level_one_sided_p=float(test.pvalue),
        v2_variables=v2_variables,v3_variables=v3_variables,
        variable_reduction_fraction=(v2_variables-v3_variables)/v2_variables,
        v2_physical_candidates=statistics.median(r['v2_physical_candidates'] for r in rows),
        v3_physical_candidates=statistics.median(r['v3_physical_candidates'] for r in rows))
    write_csv(out/'raw_planner_trials.csv',rows)
    write_csv(out/'selection_medians.csv',selections)
    write_csv(out/'history_medians.csv',histories)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')

    fig,ax = plt.subplots(figsize=(6.8,5.6),constrained_layout=True)
    x=[r['v2_median_ms'] for r in selections]
    y=[r['v3_median_ms'] for r in selections]
    lower=min(x+y)*.8; upper=max(x+y)*1.2
    ax.scatter(x,y,color='#172e57',alpha=.8)
    ax.plot([lower,upper],[lower,upper],linestyle='--',color='#a33',label='Equal planning time')
    ax.set(xscale='log',yscale='log',xlim=(lower,upper),ylim=(lower,upper),
           xlabel='Planner V2 median planning time (ms)',
           ylabel='Planner V3 median planning time (ms)',
           title='Paired opaque-boundary planner trials')
    ax.grid(alpha=.2);ax.legend()
    fig.savefig(out/'planner_v3_ablation.png',dpi=180)
    plt.close(fig)
    (out/'RUN_COMPLETE').write_text('All paired planner trials and checks completed.\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('out',type=Path)
    parser.add_argument('--trials',type=int,default=30)
    args=parser.parse_args()
    print(json.dumps(run(args.source,args.out,args.trials),indent=2))
