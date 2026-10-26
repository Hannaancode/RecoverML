"""Plot every fixed planner group without generating new measurements."""
import argparse
import json
from pathlib import Path
import random
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot(directory, output):
    complete=json.loads((directory/'complete_audit.json').read_bytes())
    if complete['status']!='PASS' or complete['frozen_conditions']!=230 or complete['scaling_conditions']!=24:
        raise ValueError('Complete passing grid required')
    reports={g:json.loads((directory/g/'planner_comparison/report.json').read_bytes())
             for g in ('scientific','cloud','retinal','letter','scaling')}
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for topology,color,label in [('independent_branches','#0072B2','Independent branches'),
                                  ('wide_frontier','#D55E00','Wide retained frontier')]:
        xs=[64,256,1024,4096]
        med=[]
        for width in xs:
            rows=[r for r in reports['scaling']['comparisons'] if r['case'].startswith(topology+'-w'+str(width)+'-')]
            values=[r['paired_speedup']['RecoverML_previous'] for r in rows]
            if len(values)!=3: raise ValueError('All three scaling seeds required')
            med.append(statistics.median(values))
            axes[0].scatter([width]*3,values,c=color,alpha=.4,s=20)
        axes[0].plot(xs,med,'-o',color=color,label=label)
    axes[0].axhline(1,color='#555555',linestyle='--',linewidth=1)
    axes[0].set(xscale='log',xticks=[64,256,1024,4096],xticklabels=['64','256','1024','4096'],
        ylim=(0,8.6),xlabel='Branches or retained-frontier width',
        ylabel='Previous / revised planning time',title='Scaling: median across three fixed seeds')
    axes[0].legend(fontsize=9)
    labels=[]
    for i,group in enumerate(('scientific','cloud','retinal','letter')):
        rows=reports[group]['comparisons']
        values=[r['paired_speedup']['RecoverML_previous'] for r in rows]
        jitter=random.Random(group)
        axes[1].scatter(values,[i+jitter.uniform(-.13,.13) for _ in values],s=20,c='#0072B2',alpha=.5)
        axes[1].scatter([statistics.median(values)],[i],marker='D',s=46,c='#111111')
        summary=reports[group]['summary']['RecoverML_previous']
        labels.append(group.title()+' ('+str(len(rows))+')')
        axes[1].text(3.7,i-.28,str(summary['indexed_faster'])+' faster / '+str(summary['indexed_slower'])+' slower',
                     ha='right',va='center',fontsize=8)
    axes[1].axvline(1,color='#555555',linestyle='--',linewidth=1)
    axes[1].set(xscale='log',xlim=(.25,4),xticks=[.25,.5,1,2,4],xticklabels=['0.25','0.5','1','2','4'],
        yticks=range(4),yticklabels=labels,ylim=(3.5,-.5),xlabel='Previous / revised planning time',
        title='Frozen histories: all cases, including slowdowns')
    axes[1].text(.03,.03,'Left of 1: revised is slower\nBlack diamonds: group medians',
                 transform=axes[1].transAxes,fontsize=8)
    for axis in axes:
        axis.grid(alpha=.2);axis.set_axisbelow(True)
    fig.suptitle('Exact-planner engineering follow-up: identical retained-byte optima',fontsize=13)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=180);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plot(args.directory,args.output)
