"""Regenerate paper tables, figures and claim inputs from complete saved runs."""
import argparse
import csv
import gzip
import hashlib
import json
import statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def analyze(source,output):
    output.mkdir(parents=True,exist_ok=False)
    def rows(group):return list(csv.DictReader((source/group/'summary.csv').open()))
    data={g:rows(g) for g in ('tabular','estimators','scaling','index','dvc')}
    reports={g:json.loads((source/g/'report.json').read_text()) for g in data}
    for group in ('tabular','estimators'):
        r=data[group]
        if sum(int(x['requests']) for x in r)!=reports[group]['requests']:raise RuntimeError('Request count mismatch')
        if sum(int(x['exact']) for x in r)!=reports[group]['exact']:raise RuntimeError('Exact count mismatch')
        if any(int(x['exact'])!=int(x['requests']) for x in r if x['policy'] in ('robust','expanded_exact','snapshots','all_groups_off')):raise RuntimeError('Protected recovery failed')
        for case in {x['case'] for x in r}:
            a=[x for x in r if x['case']==case and x['policy'] in ('robust','expanded_exact')]
            if len(a)!=2 or a[0]['retained_bytes']!=a[1]['retained_bytes']:raise RuntimeError('Exact optima disagree')
        trace=json.loads(gzip.decompress((source/group/'execution_traces.json.gz').read_bytes()))
        if len(trace)!=reports[group]['requests'] or sum(t['exact'] for t in trace)!=reports[group]['exact']:raise RuntimeError('Trace totals disagree')
        if any(not t['capture_archive_absent'] or t['end_timestamp_ns']<t['start_timestamp_ns'] for t in trace):raise RuntimeError('Trace provenance failed')
    names=['robust','expanded_exact','nominal','HYPPO_rank_component','HYPPO_frequency_component']
    labels=['RecoverML','Expanded exact','Nominal exact','HYPPO rank','HYPPO frequency']
    coverage={}
    fig,axes=plt.subplots(1,2,figsize=(10,4.4),sharey=True)
    titles=(str(reports['tabular']['captured_histories'])+' tabular histories',str(reports['estimators']['captured_histories'])+' larger model histories')
    for ax,group,title in zip(axes,('tabular','estimators'),titles):
        totals=[]
        for policy in names:
            r=[x for x in data[group] if x['policy']==policy];n=sum(int(x['requests']) for x in r);e=sum(int(x['exact']) for x in r)
            coverage[group,policy]=(e,n);totals.append(100*e/n)
        bars=ax.bar(range(5),totals,color=['#117d92','#609cab','#a0a0a0','#da8f20','#b96b29'])
        ax.bar_label(bars,labels=[f'{v:.1f}%' for v in totals],fontsize=8,padding=3)
        ax.set_xticks(range(5),labels,rotation=25,ha='right',fontsize=8);ax.set_ylim(0,115);ax.set_title(title)
    axes[0].set_ylabel('Exact requests under permitted losses (%)')
    fig.suptitle('Common robust minimum budget / same exact recovery executor',fontsize=11)
    fig.tight_layout();fig.savefig(output/'coverage_comparison.png',dpi=200);plt.close(fig)
    condition=[]
    for dataset in ('breast_cancer','iris','wine','banknote'):
        values=[]
        for fmt,k in [('npy','1'),('npy','2'),('csv6','1'),('csv6','2')]:
            s=[x for x in data['tabular'] if x['policy']=='robust' and x['dataset']==dataset and x['format']==fmt and x['k']==k]
            values.append(statistics.mean(float(x['saving_vs_snapshots']) for x in s))
        condition.append((dataset,values))
    fig,ax=plt.subplots(figsize=(8,4.4))
    for j,label in enumerate(('Lossless / 1 loss','Lossless / 2 losses','Rounded / 1 loss','Rounded / 2 losses')):
        ax.bar(np.arange(4)+(j-1.5)*.19,[v[j] for _,v in condition],width=.19,label=label)
    ax.set_xticks(range(4),['Breast Cancer','Iris','Wine','Banknote']);ax.set_ylabel('Total stored bytes saved vs snapshots (%)')
    ax.set_ylim(0,60);ax.legend(fontsize=8,ncol=2);ax.set_title('Three split seed means / twelve protected model versions')
    fig.tight_layout();fig.savefig(output/'storage_conditions.png',dpi=200);plt.close(fig)
    scaling=[]
    fig,axes=plt.subplots(1,2,figsize=(9,4),sharey=True)
    for ax,k in zip(axes,('1','2')):
        for policy,label,color in [('counterexample','RecoverML','#117d92'),('expanded_exact','Expanded exact','#da8f20')]:
            medians=[]
            for groups in (6,12,24):
                r=[x for x in data['scaling'] if x['k']==k and int(x['groups'])==groups and x['policy']==policy]
                if not all(x['analytic_match']=='True' for x in r):raise RuntimeError('Uncertified scaling comparison')
                values=[1000*float(x['elapsed_s']) for x in r];m=statistics.median(values);medians.append(m)
                ax.scatter([groups]*len(values),values,color=color,alpha=.3,s=10)
            ax.plot([6,12,24],medians,'o-',label=label,color=color)
        ax.set_yscale('log');ax.set_xticks([6,12,24]);ax.set_xlabel('Declared capability groups');ax.set_title('At most '+k+' group loss'+('es' if k=='2' else ''))
        ax.legend(fontsize=8)
    axes[0].set_ylabel('Total planning time (ms / logarithmic scale)')
    fig.tight_layout();fig.savefig(output/'planning_scaling.png',dpi=200);plt.close(fig)
    for groups in (6,12,24):
        for k in (1,2):
            s=[x for x in data['scaling'] if int(x['groups'])==groups and int(x['k'])==k]
            times={p:statistics.median(float(x['elapsed_s']) for x in s if x['policy']==p) for p in ('counterexample','expanded_exact')}
            scaling.append(dict(groups=groups,k=k,**times,speedup=times['expanded_exact']/times['counterexample']))
    kernels=[];fig,ax=plt.subplots(figsize=(7,4))
    for p,label,color in [('scan','Original scan','#da8f20'),('indexed','Dependency index','#117d92')]:
        values=[]
        for depth in (32,128,512,2048):
            s=[x for x in data['index'] if int(x['depth'])==depth and x['policy']==p]
            if not all(x['identical_certificate']=='True' for x in s):raise RuntimeError('Certificate changed')
            values.append(1000*statistics.median(float(x['elapsed_s']) for x in s))
        ax.plot([32,128,512,2048],values,'o-',label=label,color=color)
    ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_xticks([32,128,512,2048],[32,128,512,2048])
    ax.set_xlabel('Generated chain depth');ax.set_ylabel('Certificate kernel time (ms / log scale)');ax.legend()
    ax.set_title('Identical certificates / kernel only / seven timing repetitions')
    fig.tight_layout();fig.savefig(output/'certificate_index.png',dpi=200);plt.close(fig)
    for depth in (32,128,512,2048):
        s=[x for x in data['index'] if int(x['depth'])==depth]
        a=statistics.median(float(x['elapsed_s']) for x in s if x['policy']=='scan');b=statistics.median(float(x['elapsed_s']) for x in s if x['policy']=='indexed')
        kernels.append(dict(depth=depth,scan_s=a,index_s=b,speedup=a/b))
    dvc=[]
    for model in ('logistic','forest','mlp'):
        for k in ('1','2'):
            s=[x for x in data['dvc'] if x['estimator']==model and x['k']==k]
            dvc.append(dict(model=model,k=int(k),saving=statistics.mean(float(x['saving_normalized']) for x in s),
                snapshot_bytes=statistics.mean(int(x['common_snapshot_bytes']) for x in s),robust_bytes=statistics.mean(int(x['robust_bytes']) for x in s)))
    fig,ax=plt.subplots(figsize=(8,4.4))
    x=np.arange(len(dvc));ax.bar(x-.18,[r['snapshot_bytes']/1024**2 for r in dvc],.36,label='DVC normalized snapshot payload',color='#da8f20')
    ax.bar(x+.18,[r['robust_bytes']/1024**2 for r in dvc],.36,label='RecoverML robust minimum',color='#117d92')
    ax.set_xticks(x,[r['model']+'\nk='+str(r['k']) for r in dvc]);ax.set_ylabel('Common retained storage (MiB)')
    ax.set_title('Native DVC checkouts / common root and metadata accounting');ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(output/'dvc_storage.png',dpi=200);plt.close(fig)
    forest_quality=[a for q in reports['estimators']['quality'] if q['estimator']=='forest' for a in q['accuracy']]
    mlp_quality=[a for q in reports['estimators']['quality'] if q['estimator']=='mlp' for a in q['accuracy']]
    neural_total=coverage['estimators','robust']
    text=['### Verified comparison tables','',
        '| Policy | Tabular exact requests | Larger model exact requests |',
        '|---|---:|---:|']
    for p,label in zip(names,labels):
        a,b=coverage['tabular',p],coverage['estimators',p];text.append(f'| {label} | {a[0]}/{a[1]} | {b[0]}/{b[1]} |')
    text+=['','![Exact recovery at common robust budget](../results/research/paper_oct14/analysis/coverage_comparison.png)','',
        '| Dataset | Lossless k=1 saving | Lossless k=2 saving | Rounded k=1 saving | Rounded k=2 saving |','|---|---:|---:|---:|---:|']
    for dataset,v in condition:text.append('| '+dataset.replace('_',' ')+' | '+' | '.join(f'{z:.2f}%' for z in v)+' |')
    text+=['','![Storage sensitivity to format and outage bound](../results/research/paper_oct14/analysis/storage_conditions.png)','',
        '### Larger trained artifacts','',
        f"The corrected Digits experiment contains {reports['estimators']['captured_histories']} histories and {reports['estimators']['planning_cases']} planning cases and {reports['estimators']['requests']} requests across nine policies and the robust and expanded exact methods each recover {neural_total[0]} of {neural_total[1]} requests. Forests use 24 to 48 trees and depth at most twelve and the neural model uses 96 and 32 hidden units. Held out forest accuracies range from {100*min(forest_quality):.2f} to {100*max(forest_quality):.2f} percent and neural accuracies range from {100*min(mlp_quality):.2f} to {100*max(mlp_quality):.2f} percent. These are workload checks and not classification improvements.",'',
        '| Estimator | Bound | Snapshot saving | Robust exact requests |','|---|---:|---:|---:|']
    for model in ('forest','mlp'):
        for k in ('1','2'):
            s=[x for x in data['estimators'] if x['policy']=='robust' and x['estimator']==model and x['k']==k]
            text.append(f"| {model} | {k} | {statistics.mean(float(x['saving_vs_snapshots']) for x in s):.2f}% | {sum(int(x['exact']) for x in s)}/{sum(int(x['requests']) for x in s)} |")
    text+=['','### Native DVC snapshot comparison','',
        f"The native DVC experiment completes {reports['dvc']['actual_checkouts']} real per version checkouts across {len({(r['dataset'],r['estimator'],r['seed']) for r in data['dvc']})} separately captured history configurations and checks every restored model and prediction hash. The following means use two seeds and include common roots and manifest and contract bytes while DVC specific directory and pointer bytes are recorded separately.",'',
        '| Workload | Bound | Normalized DVC snapshot bytes | RecoverML bytes | Saving |','|---|---:|---:|---:|---:|']
    for r in dvc:text.append(f"| {r['model']} | {r['k']} | {r['snapshot_bytes']:.0f} | {r['robust_bytes']:.0f} | {r['saving']:.2f}% |")
    text+=['','![Normalized storage and native snapshot validation](../results/research/paper_oct14/analysis/dvc_storage.png)','',
        '### Exact planning scalability','',
        f"All {len(data['scaling'])} planner executions match the independently derived byte minimum. Timing repetitions per formulation and case rotate the solve order and the times include formulation construction and solving and post checks. These are same host repeated timings rather than independent machine samples.",'',
        '| Groups | Bound | RecoverML median ms | Expanded median ms | Expanded / RecoverML |','|---|---:|---:|---:|---:|']
    for r in scaling:text.append(f"| {r['groups']} | {r['k']} | {1000*r['counterexample']:.2f} | {1000*r['expanded_exact']:.2f} | {r['speedup']:.2f} |")
    text+=['','![Both exact formulations and their total planning time](../results/research/paper_oct14/analysis/planning_scaling.png)','',
        'At 24 groups and two losses the expanded model has 27255 variables while the storage master has seventeen and the adversary has forty one. The master and adversary are solved iteratively and these counts should not be interpreted as a single seventeen variable full optimization. Enumeration is faster in the smallest cases and the proposed advantage emerges as the scenario universe grows.','',
        '### Indexed certificate kernel','',
        '| Generated depth | Scan median ms | Index median ms | Kernel speedup |','|---|---:|---:|---:|']
    for r in kernels:text.append(f"| {r['depth']} | {1000*r['scan_s']:.3f} | {1000*r['index_s']:.3f} | {r['speedup']:.2f} |")
    text+=['','![Certificate kernel scaling](../results/research/paper_oct14/analysis/certificate_index.png)','',
        f"All {len(data['index'])} kernel timings preserve the complete certificate including producer choices and grounding rounds. The generated dependency chain result measures certificate construction only and is not a claim of the same speedup for a full model recovery request."]
    (output/'measured_results.md').write_text('\n'.join(text)+'\n')
    inputs={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for group in data for p in (source/group).iterdir() if p.is_file()}
    ledger=dict(inputs=inputs,analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),coverage={g:{p:dict(exact=coverage[g,p][0],requests=coverage[g,p][1]) for p in names} for g in ('tabular','estimators')},
        scaling=scaling,index=kernels,dvc=dvc,scope='Every count and median is derived from saved complete runs; HYPPO component and DVC snapshot scopes remain distinct')
    (output/'claim_ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    return ledger


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();analyze(args.input,args.output)
