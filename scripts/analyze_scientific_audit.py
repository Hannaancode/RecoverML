"""Validate raw requests and describe the prospectively declared audit matrix."""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import hashlib
import json
import itertools
from pathlib import Path
import numpy as np


def grid_errors(protocol, captures, rows):
    expected_histories={f'{w}-{s}' for w in protocol['workflows'] for s in protocol['seeds']}
    actual_histories=[c['history'] for c in captures]
    errors=[]
    if len(actual_histories)!=len(set(actual_histories)):errors.append('Duplicate capture history')
    if set(actual_histories)!=expected_histories:errors.append('Missing or unexpected declared capture history')
    expected={(h,scope,k,float(b),method) for h,scope,k,b,method in itertools.product(
        expected_histories,protocol['capability_scopes'],protocol['loss_bounds'],
        protocol['optional_snapshot_budget_fractions'],protocol['methods'])}
    actual=[(r['history'],r['scope'],int(r['k']),float(r['budget_fraction']),r['policy']) for r in rows]
    if len(actual)!=len(set(actual)):errors.append('Duplicate summary condition')
    if set(actual)!=expected:errors.append('Incomplete declared grid')
    return errors


def run(source):
    rows=list(csv.DictReader((source/'summary.csv').open()))
    protocol=json.loads((source/'protocol.json').read_text())
    report=json.loads((source/'report.json').read_text())
    captures=json.loads((source/'capture_inventory.json').read_text())
    expected_rows=(len(protocol['workflows'])*len(protocol['seeds'])*len(protocol['capability_scopes'])*len(protocol['loss_bounds'])
        *len(protocol['optional_snapshot_budget_fractions'])*len(protocol['methods']))
    errors=grid_errors(protocol,captures,rows);seen=set();counts=defaultdict(Counter);raw_count=0
    with gzip.open(source/'execution_traces.jsonl.gz','rt') as stream:
        for line in stream:
            t=json.loads(line);raw_count+=1
            key=(t['case'],t['policy'],t['budget_fraction'])
            identity=(*key,t['version'],tuple(t['disabled']))
            if identity in seen:errors.append('Duplicate request '+str(identity))
            seen.add(identity);counts[key]['requests']+=1
            for field in ('exact','expected_blocked','unexpected'):counts[key][field]+=int(t[field])
            if not t['capture_archive_absent']:errors.append('Capture archive visible')
            if t['end_timestamp_ns']<t['start_timestamp_ns'] or t['latency_s']<0:errors.append('Invalid time')
    for row in rows:
        key=(row['case'],row['policy'],float(row['budget_fraction']));counter=counts[key]
        for field,raw in [('requests','requests'),('exact','exact'),('blocked','expected_blocked'),('unexpected','unexpected')]:
            if int(row[field])!=counter[raw]:errors.append('Summary/raw mismatch '+str(key)+' '+field)
        if int(row['retained_bytes'])>int(row['budget_bytes']):errors.append('Budget overrun '+str(key))
        if int(row['exact'])+int(row['blocked'])+int(row['unexpected'])!=int(row['requests']):
            errors.append('Outcome partition mismatch '+str(key))
    if len(rows)!=expected_rows:errors.append('Incomplete declared grid')
    if raw_count!=report['requests']:errors.append('Request denominator mismatch')
    if report['unexpected']:errors.append('Unexpected recovery outcomes')
    plans=json.loads(gzip.decompress((source/'planner_records.json.gz').read_bytes()))
    optima=[p for p in plans if 'budget_fraction' not in p];case_optima=defaultdict(dict)
    for p in optima:case_optima[p['case']][p['policy']]=p
    disagreements=[];unknown=[]
    for case,values in case_optima.items():
        proven=[p for p in values.values() if p['status']=='ok' and p['diagnostic'].get('storage_optimal')]
        if len(proven)<2:unknown.append(case)
        elif len({p['actual_bytes'] for p in proven})>1:disagreements.append(case)
    history_metrics=[]
    for history in sorted({r['history'] for r in rows}):
        selected=[r for r in rows if r['history']==history]
        for policy in protocol['methods']:
            matched=[r for r in selected if r['policy']==policy]
            history_metrics.append(dict(history=history,policy=policy,
                mean_condition_coverage=float(np.mean([int(r['exact'])/int(r['requests']) for r in matched])),
                complete_conditions=sum(r['complete']=='True' for r in matched),conditions=len(matched),
                note='Descriptive mean over correlated fixed scopes and budgets and loss bounds'))
    complete=[r for r in rows if r['complete']=='True']
    baseline_gaps=[]
    for row in complete:
        if row['policy'] not in ('robust_greedy','robust_local'):continue
        optimum=case_optima[row['case']]['RecoverML_exact']
        if optimum['status']=='ok':
            baseline_gaps.append(dict(case=row['case'],policy=row['policy'],budget_fraction=float(row['budget_fraction']),
                excess_bytes=int(row['retained_bytes'])-optimum['actual_bytes']))
    data=dict(status='PASS' if not errors else 'FAIL',rows=len(rows),expected_rows=expected_rows,
        requests=raw_count,histories=len(captures),workflow_families=len({c['workflow'] for c in captures}),
        errors=errors,independent_formulation_cases=len(case_optima),optimum_disagreements=disagreements,
        solver_unknown_cases=unknown,unexpected_requests=report['unexpected'],
        capture_or_planning_failures=report['failures'],
        history_metrics=history_metrics,heuristic_complete_gaps=baseline_gaps,
        statistical_qualification='Descriptive constructed history-level summaries; no iid production sample or acceptance guarantee',
        raw_sha256=hashlib.sha256((source/'execution_traces.jsonl.gz').read_bytes()).hexdigest())
    (source/'analysis.json').write_text(json.dumps(data,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    policies=[p for p in protocol['methods'] if p!='scenario_exact']
    colors={p:plt.get_cmap('tab10')(i) for i,p in enumerate(policies)}
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),sharey=True)
    for scope,ax in zip(protocol['capability_scopes'],axes):
        for policy in policies:
            values=[]
            for fraction in protocol['optional_snapshot_budget_fractions']:
                matched=[r for r in rows if r['policy']==policy and r['scope']==scope and int(r['k'])==1 and float(r['budget_fraction'])==fraction]
                values.append(100*np.mean([int(r['exact'])/int(r['requests']) for r in matched]))
            ax.plot(protocol['optional_snapshot_budget_fractions'],values,marker='o',label=policy,color=colors[policy],linewidth=1.2)
        ax.set_title(scope+' group losses, k=1');ax.set_xlabel('Fraction of optional target snapshot payload budget');ax.grid(alpha=.25)
    axes[0].set_ylabel(f'Mean exact request coverage across {len(captures)} histories (%)')
    axes[1].legend(fontsize=7,loc='best');fig.tight_layout();fig.savefig(source/'common_budget_coverage.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,8))
    for workflow,ax in zip(protocol['workflows'],axes.flat):
        for policy in policies:
            matched=[r for r in complete if r['workflow']==workflow and r['scope']=='preprocessing' and int(r['k'])==1 and r['policy']==policy]
            if matched:
                x=[int(r['retained_bytes'])/(int(r['fixed_bytes'])+int(r['snapshot_target_payload_bytes'])) for r in matched]
                y=[float(r['latency_mean_s'])*1000 for r in matched]
                ax.scatter(x,y,label=policy,color=colors[policy],s=24,alpha=.7)
        ax.set_title(workflow);ax.set_xlabel('Actual bytes / full target snapshot bytes');ax.set_ylabel('Mean end-to-end recovery latency (ms)')
        ax.set_yscale('log');ax.grid(alpha=.25)
    handles,labels=axes.flat[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=4,fontsize=8)
    fig.suptitle('Complete recovery only, preprocessing k=1, both seeds and all declared budgets')
    fig.tight_layout(rect=(0,.08,1,.96));fig.savefig(source/'storage_recovery_tradeoff.png',dpi=180);plt.close(fig)
    lines=['# Supplementary scientific audit results','',
        f"Raw reconciliation: **{data['status']}** across {len(rows)} rows and {raw_count} real requests",'',
        f"There are {len(captures)} constructed captures from four fixed recipe adaptations and two seeds each",
        'Conditions and repeated requests from a capture are correlated and are not additional independent samples','',
        f"Both exact formulations were attempted on {len(case_optima)} cases with {len(disagreements)} optimum disagreements and {len(unknown)} unproved cases",'',
        f"Unexpected recovery outcomes: {report['unexpected']}",
        'Expected blocked requests and zero-saving conditions remain in the raw evidence and summary','',
        'The exact minimum policies report infeasible below their minimum byte requirement and do not claim to maximize partial coverage',
        'The complete-only latency plot must be read with the coverage plot to avoid a successful-only comparison','',
        '| Method | Exact / requests over the full declared grid | Complete conditions / conditions |',
        '|---|---:|---:|']
    for p in protocol['methods']:
        matched=[r for r in rows if r['policy']==p]
        lines.append(f"| {p} | {sum(int(r['exact']) for r in matched)} / {sum(int(r['requests']) for r in matched)} | {sum(r['complete']=='True' for r in matched)} / {len(matched)} |")
    lines+=['','These pooled counts describe this fixed matrix and do not establish population significance',
        'Costs include manifest parsing and grounded planning and model loading or retraining and dependency recovery',
        'One trial per request does not establish stable tail-latency estimates or device-level I/O or energy','',
        'The source snapshots and protocol hash and full planners and sensitivity rows are included',
        'The recipes have no deliberately inserted equal-output producers and remain constructed histories rather than observed production histories']
    (source/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    if errors or disagreements:raise RuntimeError('Scientific audit reconciliation failed')
    return {k:v for k,v in data.items() if k not in ('history_metrics','heuristic_complete_gaps')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args();print(json.dumps(run(a.source),indent=2))
