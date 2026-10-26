"""Derive tables and complete speedup distributions from an audited census."""
import argparse
import csv
import json
from pathlib import Path
import statistics


def summarize(audit,output):
    result=json.loads(Path(audit).read_bytes())
    if result['status']!='PASS':raise ValueError('Exactness audit must pass')
    rows=[r for b in result['blocks'] for r in b['comparisons']]
    if len(rows)!=864:raise ValueError('Complete frozen census required')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    def aggregate(subset):
        d=[r['ratio_dvc_to_recoverml'] for r in subset]
        c=[r['median_s']['direct_control']/r['median_s']['RecoverML'] for r in subset]
        return dict(cases=len(subset),dvc_substantial_wins=sum(v>=1.1 for v in d),
            median_dvc_to_recoverml=statistics.median(d),minimum_dvc_to_recoverml=min(d),
            maximum_dvc_to_recoverml=max(d),direct_faster_cases=sum(v>1 for v in c),
            direct_substantial_wins=sum(v>=1.1 for v in c),
            direct_substantial_losses=sum(v<=1/1.1 for v in c),
            median_direct_to_recoverml=statistics.median(c),
            median_elapsed_s={m:statistics.median(r['median_s'][m] for r in subset)
                              for m in ('RecoverML','DVC_native','direct_control')})
    summary=dict(overall=aggregate(rows),interfaces={i:aggregate([r for r in rows if r['case'].endswith('/'+i)])
        for i in ('cli','warm_api')},availability={str(value):aggregate([r for r in rows if r['all_requested_retained']==value])
        for value in (False,True)},qualification=result['qualification'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    with (output/'all_comparisons.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['case','recoverml_median_s','dvc_median_s','direct_median_s',
            'dvc_to_recoverml','direct_to_recoverml','all_requested_retained'])
        for r in rows:
            writer.writerow([r['case'],r['median_s']['RecoverML'],r['median_s']['DVC_native'],
                r['median_s']['direct_control'],r['ratio_dvc_to_recoverml'],
                r['median_s']['direct_control']/r['median_s']['RecoverML'],r['all_requested_retained']])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.4),layout='constrained')
    for interface,label,color in [('cli','CLI','#31688e'),('warm_api','Warm API','#35b779')]:
        subset=[r for r in rows if r['case'].endswith('/'+interface)]
        for ax,method in zip(axes,['DVC_native','direct_control']):
            values=sorted(r['median_s'][method]/r['median_s']['RecoverML'] for r in subset)
            ax.step(values,[(i+1)/len(values) for i in range(len(values))],where='post',color=color,label=label+' (432)')
    for ax,method in zip(axes,['DVC','Direct executor']):
        ax.axvline(1,color='#444444',linewidth=1,label='Parity')
        ax.axvline(1.1,color='#bd533d',linestyle='--',linewidth=1,label='1.10x threshold')
        ax.set_xlabel(method+' median time / RecoverML median time')
        ax.set_ylim(0,1.02);ax.grid(alpha=.2);ax.legend(fontsize=8,loc='lower right')
    axes[0].set_xscale('log');axes[0].set_ylabel('Cumulative fraction of catalogue configurations')
    axes[0].set_title('Native DVC: every configuration exceeds 1.10x')
    axes[1].set_title('Direct executor: near parity, with losses retained')
    fig.suptitle('Complete fixed recovery census: 864 configurations, three paired trials per method',fontsize=12)
    fig.savefig(output/'speedup_distributions.png',dpi=180)
    fig.savefig(output/'speedup_distributions.svg')
    svg=output/'speedup_distributions.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                   encoding='utf-8',newline='\n')
    plt.close(fig)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(summarize(args.audit,args.output),indent=2))
