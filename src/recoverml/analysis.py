"""Recompute result tables/plots from execution records; no invented measurements."""
import csv
import json
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .benchmark import write_csv

POLICIES=['full_snapshot','full_replay','cost_cache','pinned_cost','target_snapshots','recoverability','recoverability_v2','recoverability_v3']
LABELS=['Full snapshots','Full replay','Cost cache','Pinned boundaries','Target snapshots','Planner v1','Planner v2','Planner v3']
COLORS=['#737373','#ba4a00','#a569bd','#2471a3','#17a589','#8299b5','#496a9a','#172e57']


def boolean(v):
    return str(v).lower()=='true'


def analyze(directory: Path):
    rows=list(csv.DictReader((directory/'raw_requests.csv').open()))
    groups=defaultdict(list)
    for r in rows:
        r['exact']=boolean(r['exact'])
        r['within_budget']=boolean(r['within_budget'])
        r['protect_intermediate']=boolean(r['protect_intermediate'])
        for k in ('budget_fraction','retained_bytes','full_bytes','planning_s'):
            r[k]=float(r[k])
        r['restore_s']=float(r['restore_s']) if r['restore_s'] else None
        groups[(r['policy'],r['budget_fraction'])].append(r)
    table=[]
    for (policy,budget),rs in sorted(groups.items()):
        good=[r for r in rs if r['exact']]
        times=[r['restore_s'] for r in good]
        table.append(dict(policy=policy,budget_fraction=budget,requests=len(rs),
            successes=len(good),success_rate=len(good)/len(rs),
            budget_blocked=sum(not r['within_budget'] for r in rs),
            restoration_failed=sum(r['status']=='restore_failed' for r in rs),
            median_successful_restore_ms=float(np.median(times)*1000) if times else '',
            p95_successful_restore_ms=float(np.percentile(times,95)*1000) if times else '',
            median_retained_fraction=float(np.median([r['retained_bytes']/r['full_bytes'] for r in good])) if good else '',
            median_planning_ms=float(np.median([r['planning_s'] for r in rs])*1000)))
    write_csv(directory/'summary.csv',table)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    budgets=sorted({r['budget_fraction'] for r in rows})
    active=[(p,l,c) for p,l,c in zip(POLICIES,LABELS,COLORS) if any(r['policy']==p for r in rows)]
    policies,labels,colors=zip(*active)
    fig,ax=plt.subplots(figsize=(10.5,5.2),constrained_layout=True)
    for p,label,color in active:
        data=[next(t for t in table if t['policy']==p and t['budget_fraction']==b)['success_rate']*100 for b in budgets]
        ax.plot(np.arange(len(budgets)),data,marker='o',label=label,color=color,linewidth=2)
    ax.set(xticks=np.arange(len(budgets)),xticklabels=[f'{b:.0%}' for b in budgets],ylim=(-3,103),
           xlabel='Budget / deduplicated full-snapshot bytes (includes inputs and manifest)',
           ylabel='Exactly restored requests (%)',title='All requests counted, including budget-blocked cases')
    ax.grid(axis='y',alpha=.2);ax.legend(ncol=3,loc='lower right',fontsize=9)
    fig.savefig(directory/'success_by_budget.png',dpi=180);plt.close(fig)
    # One controlled workload; no mixing model sizes or restoration scopes.
    example=[r for r in rows if r['dataset']=='synthetic' and int(r['rows'])==10000
             and r['boundary']=='opaque' and r['change']=='parameters' and not r['protect_intermediate']
             and int(r.get('branches',1))==1]
    example_budget=.25
    example_title='10,000-row opaque-feature history, 5 versions, 5 independent repeats'
    if not example:
        # Public-data transfer studies do not contain the historical synthetic
        # case. Use all declared opaque histories instead of producing a blank plot.
        example=[r for r in rows if r['boundary']=='opaque'
                 and r['change']=='parameters' and not r['protect_intermediate']
                 and int(r.get('branches',1))==1]
        example_budget=.4 if .4 in budgets else budgets[len(budgets)//2]
        histories=len({r['case_id'] for r in example})
        datasets=', '.join(sorted({r['dataset'].title() for r in example}))
        example_title=f'{datasets} opaque-feature study, {histories} captured histories'
    fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    xs=np.arange(len(policies))
    panel_values=[]
    annotations=[]
    retained=[]
    for p in policies:
        budget=1.0 if p=='full_snapshot' else example_budget
        records=[r for r in example if r['policy']==p and r['budget_fraction']==budget]
        good=[r for r in records if r['exact']]
        panel_values.append(100*len(good)/len(records) if records else 0.)
        annotations.append(f'{len(good)}/{len(records)} exact')
        retained.append(100*np.median([r['retained_bytes']/r['full_bytes'] for r in good]) if good else 0.)
    for j,vals in enumerate((panel_values,retained)):
        ax=axs[j];ax.bar(xs,vals,color=colors)
        ax.set(xticks=xs,xticklabels=labels,
               ylabel='Exactly restored requests (%)' if j==0 else 'Median retained fraction (%)')
        ax.set_ylim(0,108)
        ax.tick_params(axis='x',rotation=35,labelsize=8)
        for x,y,annotation in zip(xs,vals,annotations):
            ax.annotate(annotation,(x,y),xytext=(0,5),textcoords='offset points',ha='center',fontsize=8)
        ax.grid(axis='y',alpha=.2)
    fig.suptitle(f'{example_title}\nFull snapshots use 100% budget and other policies use {example_budget:.0%}')
    fig.savefig(directory/'opaque_workload.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.6),constrained_layout=True)
    values=[]
    for p in policies:
        records=[r for r in rows if r['policy']==p and r['budget_fraction']==.5]
        values.append(np.median([r['planning_s'] for r in records])*1000)
    ax.bar(labels,values,color=colors)
    ax.set(ylabel='Median planning time per history (ms)',title='Planning overhead is separate from restore latency (50% budget)')
    ax.tick_params(axis='x',rotation=25,labelsize=9)
    for i,v in enumerate(values):ax.text(i,v,f'{v:.1f}',ha='center',va='bottom')
    fig.savefig(directory/'planning_overhead.png',dpi=180);plt.close(fig)
    unexpected=[r for r in rows if r['status']=='restore_failed' and 'non-replayable' not in r['error']]
    proposed_name=('recoverability_v3' if 'recoverability_v3' in policies else
                   'recoverability_v2' if 'recoverability_v2' in policies else 'recoverability')
    proposed=[r for r in rows if r['policy']==proposed_name]
    proposed_admitted=[r for r in proposed if r['within_budget']]
    report=dict(total_requests=len(rows),status_counts=dict(Counter(r['status'] for r in rows)),
        unexpected_failures=len(unexpected),proposed_admitted=len(proposed_admitted),
        proposed_exact=sum(r['exact'] for r in proposed_admitted),
        proposed_budget_blocked=sum(not r['within_budget'] for r in proposed),summary=table)
    (directory/'findings.json').write_text(json.dumps(report,indent=2))
    return report
