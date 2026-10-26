"""Create complete storage tables and scientific figures from a release audit."""
import argparse
import csv
import io
import json
from pathlib import Path
import statistics
import zipfile

from benchmark_planner_efficiency import frozen


def summarize(audit,evidence,output):
    audit=json.loads(Path(audit).read_bytes());output=Path(output);evidence=Path(evidence)
    if audit['status']!='PASS':raise ValueError('Complete release audit must pass')
    output.mkdir(parents=True,exist_ok=True)
    rows=[r for b in audit['primary']['blocks'] for r in b['comparisons']]
    stronger={r['case']:r for block in audit['strengthened_gzip']['primary'].values() for r in block['comparisons']}
    if len(rows)!=216 or set(stronger)!={r['case'] for r in rows}:raise ValueError('Complete fixed catalogue required')
    def aggregate(subset):
        saves=[stronger[r['case']]['saving'] for r in subset]
        return dict(conditions=len(subset),raw_10pct_wins=sum(r['saving_vs_raw']>=.1 for r in subset),
            median_raw_saving=statistics.median(r['saving_vs_raw'] for r in subset),
            minimum_raw_saving=min(r['saving_vs_raw'] for r in subset),maximum_raw_saving=max(r['saving_vs_raw'] for r in subset),
            strengthened_gzip_wins=sum(v>0 for v in saves),strengthened_gzip_10pct_wins=sum(v>=.1 for v in saves),
            median_strengthened_gzip_saving=statistics.median(saves),minimum_strengthened_gzip_saving=min(saves),
            maximum_strengthened_gzip_saving=max(saves),
            reselection_wins=sum(r['saving_from_reselection']>0 for r in subset),
            maximum_reselection_saving=max(r['saving_from_reselection'] for r in subset),
            local_wins=sum(r['sizes']['adaptive_exact']<r['sizes']['adaptive_local'] for r in subset),
            maximum_local_saving=max(1-r['sizes']['adaptive_exact']/r['sizes']['adaptive_local'] for r in subset),
            snapshot_wins=sum(r['sizes']['adaptive_exact']<r['sizes']['adaptive_snapshots'] for r in subset),
            median_snapshot_saving=statistics.median(1-r['sizes']['adaptive_exact']/r['sizes']['adaptive_snapshots'] for r in subset))
    strata={}
    for column,name in [(0,'dataset'),(1,'recipe'),(3,'loss')]:
        strata[name]={value:aggregate([r for r in rows if r['case'].split('/')[column]==value])
            for value in sorted({r['case'].split('/')[column] for r in rows})}
    summary=dict(overall=aggregate(rows),strata=strata,primary_counts={k:v for k,v in audit['primary'].items() if k not in ('blocks','strata')},
        transfer=audit['transfer'],stronger_transfer={g:{k:v for k,v in result.items() if k!='comparisons'}
            for g,result in audit['strengthened_gzip']['transfer'].items()},qualification=audit['qualification'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    with (output/'all_primary_conditions.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['case','raw_exact_bytes','original_gzip_exact_bytes','stronger_gzip_exact_bytes',
            'adaptive_exact_bytes','adaptive_local_bytes','adaptive_snapshot_bytes','adaptive_raw_choice_bytes',
            'saving_vs_raw','saving_vs_strengthened_gzip','saving_from_reselection'])
        for r in rows:
            s=r['sizes'];writer.writerow([r['case'],s['raw_exact'],s['gzip_exact'],stronger[r['case']]['strong_gzip_bytes'],
                s['adaptive_exact'],s['adaptive_local'],s['adaptive_snapshots'],s['adaptive_raw_choice'],r['saving_vs_raw'],
                stronger[r['case']]['saving'],r['saving_from_reselection']])
    manifest=json.loads((evidence/'artifact_manifest.json').read_bytes())
    letter=next(r for r in manifest['artifacts'] if r['kind']=='transfer' and r['group']=='letter')
    raw=b''.join((evidence/p['path']).read_bytes() for p in letter['parts'])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:letter_rows={r['case']:r for r in json.loads(z.read('encoded_transfer/conditions.json'))}
    with (output/'all_frozen_conditions.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['group','case','status','raw_exact_bytes','adaptive_bytes','gzip_control_bytes','control_scope'])
        for group in manifest['transfer_groups']:
            table={r['case']:r for r in audit['strengthened_gzip']['transfer'][group]['comparisons']}
            for case,_,_,_,expected in frozen(group,{}):
                if case in table:
                    row=table[case];writer.writerow([group,case,'COMPLETE',expected,row['adaptive_bytes'],row['strong_gzip_bytes'],'strengthened exact'])
                else:
                    row=letter_rows[case];a=row['methods'].get('adaptive_raw_choice');g=row['methods'].get('gzip_raw_choice')
                    writer.writerow([group,case,row['status'],expected,None if a is None else a['bytes'],None if g is None else g['bytes'],
                                     'fixed old selection only' if a else 'unavailable'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
    for label,values,color in [('Raw exact frontier',[r['saving_vs_raw']*100 for r in rows],'#31688e'),
                              ('Strengthened gzip frontier',[stronger[r['case']]['saving']*100 for r in rows],'#35b779')]:
        values=sorted(values);axes[0].step(values,[(i+1)/len(values) for i in range(len(values))],where='post',label=label+' (216)',color=color)
    axes[0].axvline(10,color='#bd533d',linestyle='--',linewidth=1,label='10% saving')
    axes[0].set_xlim(0,100);axes[0].set_ylim(0,1.02);axes[0].set_xlabel('Reduction in complete persistent file bytes (%)')
    axes[0].set_ylabel('Cumulative fraction of configurations');axes[0].legend(fontsize=8,loc='center',bbox_to_anchor=(.42,.55))
    axes[0].set_title('Complete distribution of paired storage reductions')
    labels=list(strata['dataset']);xs=list(range(len(labels)))
    axes[1].bar([x-.2 for x in xs],[strata['dataset'][d]['median_raw_saving']*100 for d in labels],width=.4,color='#31688e',label='Raw exact')
    axes[1].bar([x+.2 for x in xs],[strata['dataset'][d]['median_strengthened_gzip_saving']*100 for d in labels],width=.4,color='#35b779',label='Strengthened gzip')
    axes[1].set_xticks(xs,[d.replace('breast_cancer','Breast\nCancer').replace('linnerud','Linnerud').title() for d in labels],rotation=15)
    axes[1].set_ylabel('Median paired storage reduction (%)');axes[1].set_title('All six datasets, 36 conditions each');axes[1].legend(fontsize=8)
    for ax in axes:ax.grid(axis='y',alpha=.2)
    fig.suptitle('Original artifact hashes preserved: 72 captures and 216 storage conditions',fontsize=12)
    fig.savefig(output/'storage_comparison.png',dpi=180);fig.savefig(output/'storage_comparison.svg');plt.close(fig)
    svg=output/'storage_comparison.svg';svg.write_text('\n'.join(s.rstrip() for s in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    fig,ax=plt.subplots(figsize=(8,4.4),layout='constrained')
    for name,label,color in [('adaptive_local','Strong local search','#440154'),('adaptive_raw_choice','Compress raw optimum','#31688e'),
                             ('adaptive_snapshots','Target snapshots','#35b779')]:
        values=sorted((1-r['sizes']['adaptive_exact']/r['sizes'][name])*100 for r in rows)
        ax.step(values,[(i+1)/len(values) for i in range(len(values))],where='post',label=label+' (216)',color=color)
    ax.set_xlabel('Storage reduction at the same adaptive encoding (%)');ax.set_ylabel('Cumulative fraction of configurations')
    ax.set_title('Decision controls: ties remain in the full denominator');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(output/'same_codec_controls.png',dpi=180);plt.close(fig)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=summarize(args.audit,args.evidence,args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in ('strata','primary_counts','transfer','stronger_transfer')},indent=2))
