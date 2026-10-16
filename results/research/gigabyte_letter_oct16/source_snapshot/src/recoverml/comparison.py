"""Paired history comparisons; planning is charged once per five requests.

No failed selection is assigned a latency. Cost ratios use only histories where
both policies restore EVERY protected version exactly within the same budget.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from .benchmark import write_csv


def analyze_comparison(out):
    rows = list(csv.DictReader((out/'raw_requests.csv').open()))
    groups = defaultdict(list)
    for r in rows:
        groups[(r['case_id'],r['budget_fraction'],r['policy'])].append(r)
    histories = []
    indexed = {}
    for (case_id,budget,policy),rs in sorted(groups.items()):
        good = [r for r in rs if r['exact']=='True']
        all_exact = len(good)==len(rs)
        restore_sum = sum(float(r['restore_s']) for r in good) if all_exact else None
        planning = float(rs[0]['planning_s'])
        h = dict(case_id=case_id,case=case_id.split('-')[0],repeat=rs[0]['repeat'],
            policy=policy,budget_fraction=float(budget),requests=len(rs),exact=len(good),
            all_versions_exact=all_exact,planning_s=planning,retained_bytes=int(rs[0]['retained_bytes']),
            full_bytes=int(rs[0]['full_bytes']),restore_sum_s=restore_sum if all_exact else '',
            plan_and_one_history_restore_s=planning+restore_sum if all_exact else '')
        histories.append(h); indexed[(case_id,budget,policy)] = h
    write_csv(out/'history_comparison.csv',histories)
    paired = []
    for (case_id,budget,policy),new in indexed.items():
        if policy!='recoverability_v2':
            continue
        for baseline in sorted({r['policy'] for r in rows}-{'recoverability_v2'}):
            old = indexed[(case_id,budget,baseline)]
            if not (new['all_versions_exact'] and old['all_versions_exact']):
                continue
            paired.append(dict(case_id=case_id,case=new['case'],baseline=baseline,
                budget_fraction=float(budget),requests=new['requests'],
                baseline_planning_s=old['planning_s'],v2_planning_s=new['planning_s'],
                baseline_restore_sum_s=old['restore_sum_s'],v2_restore_sum_s=new['restore_sum_s'],
                baseline_plan_and_restore_s=old['plan_and_one_history_restore_s'],
                v2_plan_and_restore_s=new['plan_and_one_history_restore_s'],
                planning_speedup=old['planning_s']/new['planning_s'],
                restore_speedup=old['restore_sum_s']/new['restore_sum_s'],
                plan_and_restore_speedup=old['plan_and_one_history_restore_s']/new['plan_and_one_history_restore_s'],
                baseline_retained_bytes=old['retained_bytes'],v2_retained_bytes=new['retained_bytes']))
    write_csv(out/'paired_comparison.csv',paired)
    stats = {}
    for p in sorted({r['baseline'] for r in paired}):
        rs = [r for r in paired if r['baseline']==p]
        stats[p] = dict(paired_feasible_histories=len(rs),
            median_planning_speedup=float(np.median([r['planning_speedup'] for r in rs])),
            median_restore_speedup=float(np.median([r['restore_speedup'] for r in rs])),
            median_plan_and_restore_speedup=float(np.median([r['plan_and_restore_speedup'] for r in rs])),
            v2_faster_plan_and_restore=sum(r['plan_and_restore_speedup']>1 for r in rs))
    plans = [json.loads(line) for line in (out/'retention_plans.jsonl').read_text().splitlines()]
    strategies = Counter()
    solver_status = Counter()
    for p in plans:
        if p['policy']=='recoverability_v2':
            h = p['eviction_trace']
            strategies[h[0]['strategy'] if h else p['status']] += 1
            if h and 'solver_status' in h[0]:
                solver_status[str(h[0]['solver_status'])] += 1
    findings = dict(paired=stats,v2_strategies=dict(strategies),solver_status_counts=dict(solver_status),
        selection_counts={p:dict(total=sum(h['policy']==p for h in histories),
            all_versions_exact=sum(h['policy']==p and h['all_versions_exact'] for h in histories))
            for p in sorted({r['policy'] for r in rows})},
        qualification='Paired costs include one planning call plus one measured restoration of each version; excludes store copying and environment initialization. Warm OS cache. No imputation for failures.')
    (out/'comparison_findings.json').write_text(json.dumps(findings,indent=2)+'\n')
    plot(out,rows,histories,paired)
    return findings


def plot(out,rows,histories,paired):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False})
    cases = sorted({h['case'] for h in histories})
    fig,axes = plt.subplots(1,2,figsize=(13,5.4),constrained_layout=True)
    colors = {'recoverability':'#8299b5','recoverability_v2':'#172e57','target_snapshots':'#17a589'}
    for policy in colors:
        x=[];y=[]
        for i,case in enumerate(cases):
            rs = [h for h in histories if h['case']==case and h['policy']==policy and h['all_versions_exact']]
            if rs:
                x.append(i);y.append(np.median([h['planning_s'] for h in rs])*1000)
        axes[0].plot(x,y,'o-',label=policy,color=colors[policy])
    axes[0].set(yscale='log',xticks=range(len(cases)),xticklabels=cases,
        ylabel='Median planning time (ms, log scale)',title='Feasible plans, all budgets; simple baseline retained')
    axes[0].tick_params(axis='x',rotation=60,labelsize=8);axes[0].legend(fontsize=8)
    for policy,offset in [('recoverability',-.13),('target_snapshots',.13)]:
        xs=[];ys=[]
        for i,case in enumerate(cases):
            rs = [r for r in paired if r['case']==case and r['baseline']==policy]
            if rs:
                xs.append(i+offset);ys.append(np.median([r['plan_and_restore_speedup'] for r in rs]))
        axes[1].scatter(xs,ys,label=f'v2 vs {policy}',color=colors[policy],s=45)
    axes[1].axhline(1,color='black',ls='--',lw=1)
    axes[1].set(yscale='log',xticks=range(len(cases)),xticklabels=cases,
        ylabel='Median paired speedup (baseline / v2)',title='Planning + five restores; above 1 favors v2')
    axes[1].tick_params(axis='x',rotation=60,labelsize=8);axes[1].legend(fontsize=8)
    for ax in axes: ax.grid(axis='y',alpha=.2)
    fig.savefig(out/'paired_costs.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
    print(json.dumps(analyze_comparison(p.parse_args().directory),indent=2))
