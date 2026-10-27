"""Summarize every delta condition, including nonwins, missing data and controls."""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import json
from pathlib import Path
import statistics

from audit_encoded_storage import require
from recoverml.core import digest

ROOT=Path(__file__).resolve().parents[1]


def summarize(originals,stronger):
    config=json.loads((ROOT/'configs/delta_storage_oct27.json').read_bytes())
    prior=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    blocks=['primary/'+d+'/'+r for d in prior['datasets'] for r in prior['recipes']]+['transfer/'+g for g in config['transfer_conditions']]
    rows=[];receipts=[];commits=set()
    for key in blocks:
        path=Path(originals)/key;items=json.loads((path/'conditions.json').read_bytes());receipt=json.loads((path/'runner_audit.json').read_bytes())
        require(receipt['status']=='PASS' and not receipt['preflight'] and receipt['block']==key and receipt['conditions_sha256']==digest((path/'conditions.json').read_bytes()),'Audited block identity differs')
        require(receipt['conditions']==len(items),'Audited condition count differs');receipts.append(receipt);commits.add(receipt['source_commit'])
        strong_rows={r['case']:r for r in stronger[key]['rows']}
        require(len(strong_rows)==len(items) and stronger[key]['conditions']==len(items),'Stronger local denominator differs')
        for item in items:
            row=dict(block=key,case=item['case'],status=item['status'],production_format=item.get('production_format'))
            strong=strong_rows[item['case']];require(strong['status']==item['status'],'Stronger local condition differs')
            for method in config['methods']:row[method+'_bytes']=item['methods'].get(method,{}).get('bytes')
            row['production_bytes']=item.get('production_bytes')
            row['strong_local_bytes']=strong.get('strong_local_bytes')
            if row['status']=='COMPLETE':
                require(strong['production_bytes']==row['production_bytes'] and row['strong_local_bytes']==min(strong['options'].values()),'Stronger local choice differs')
            row['saving_over_flat']=1-row['production_bytes']/row['flat_exact_bytes'] if row['production_bytes'] is not None else None
            row['saving_over_solid']=1-row['production_bytes']/row['solid_archive_control_bytes'] if row['production_bytes'] is not None else None
            rows.append(row)
    require(len(rows)==config['primary_conditions']+sum(config['transfer_conditions'].values()) and len(commits)==1,'Incomplete or mixed-source delta census')
    def comparison(values,a,b):
        known=[r for r in values if r[a] is not None and r[b] is not None]
        savings=[1-r[a]/r[b] for r in known]
        return dict(denominator=len(values),measured=len(known),wins=sum(r[a]<r[b] for r in known),ties=sum(r[a]==r[b] for r in known),
            losses=sum(r[a]>r[b] for r in known),unmeasured=len(values)-len(known),at_least_10_percent=sum(x>=.1 for x in savings),
            median_saving=statistics.median(savings) if savings else None,min_saving=min(savings) if savings else None,max_saving=max(savings) if savings else None)
    groups={}
    for name in ['primary']+list(config['transfer_conditions']):
        subset=[r for r in rows if r['block'].startswith('primary/')] if name=='primary' else [r for r in rows if r['block']=='transfer/'+name]
        groups[name]=dict(conditions=len(subset),statuses=dict(Counter(r['status'] for r in subset)),
            production_vs_flat=comparison(subset,'production_bytes','flat_exact_bytes'),
            production_vs_solid=comparison(subset,'production_bytes','solid_archive_control_bytes'),
            same_format_local=comparison(subset,'delta_exact_bytes','delta_local_bytes'),
            strong_local_control=comparison(subset,'production_bytes','strong_local_bytes'),
            same_format_snapshots=comparison(subset,'delta_exact_bytes','delta_snapshots_bytes'),
            selection_gain=comparison(subset,'delta_exact_bytes','delta_flat_choice_bytes'))
    strata=defaultdict(list)
    for row in rows:
        if row['block'].startswith('primary/'):
            dataset,recipe,version,loss=row['case'].split('/');strata[(dataset,recipe,loss)].append(row)
    gates=[]
    for (dataset,recipe,loss),items in sorted(strata.items()):
        require(len(items)==3,'Primary stratum denominator differs')
        wins=sum(r['saving_over_flat'] is not None and r['saving_over_flat']>=config['primary_success_gate']['minimum_saving_over_flat_exact'] for r in items)
        gates.append(dict(dataset=dataset,recipe=recipe,loss=loss,conditions=3,substantial_wins=wins,
            passed=wins/3>=config['primary_success_gate']['minimum_fraction_each_primary_dataset_recipe_loss']))
    require(len(gates)==72,'Primary stratum count differs')
    complete=sum(r['status']=='COMPLETE' for r in rows)
    summary=dict(status='PASS',source_commit=next(iter(commits)),conditions=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
        selected_payloads_verified=sum(r['selected_payloads_verified'] for r in receipts),groups=groups,
        overall_vs_flat=comparison(rows,'production_bytes','flat_exact_bytes'),overall_vs_solid=comparison(rows,'production_bytes','solid_archive_control_bytes'),
        same_format_local=comparison(rows,'delta_exact_bytes','delta_local_bytes'),
        strong_local_control=comparison(rows,'production_bytes','strong_local_bytes'),
        same_format_oracle=dict(denominator=len(rows),ties=complete,wins=0,losses=0,unmeasured=len(rows)-complete),
        primary_gate_passed=all(r['passed'] for r in gates),primary_gate_strata_passed=sum(r['passed'] for r in gates),primary_strata=gates,
        qualification=config['qualification'])
    return summary,rows


def write(originals,output):
    output=Path(output);stronger=json.loads(gzip.decompress((output/'strengthened_local.json.gz').read_bytes()))
    summary,rows=summarize(originals,stronger);output.mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    with (output/'all_conditions.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    colors=['#16806a','#c0c5cb','#c4453b','#eceeef'];labels=['Win','Tie','Loss','Unmeasured']
    names=['Primary','Scientific','Cloud','Retinal','Letter'];keys=['primary','scientific','cloud','retinal','letter']
    for ax,field,title in zip(axes,['production_vs_flat','production_vs_solid'],['Against previous flat optimum','Against adaptive solid archive control']):
        left=np.zeros(5)
        for key,color,label in zip(['wins','ties','losses','unmeasured'],colors,labels):
            counts=[summary['groups'][g][field][key] for g in keys]
            ax.barh(names,counts,left=left,color=color,label=label)
            for i,count in enumerate(counts):
                if count>=8:ax.text(left[i]+count/2,i,str(count),ha='center',va='center',fontsize=9)
                elif count:ax.annotate(str(count),(left[i]+count/2,i),xytext=(12,12),textcoords='offset points',
                    ha='center',va='bottom',fontsize=9,arrowprops=dict(arrowstyle='-',color='#444444',linewidth=.6))
            left+=np.array(counts)
        ax.set_title(title,fontsize=11);ax.set_xlabel('All fixed conditions');ax.invert_yaxis();ax.spines[['top','right']].set_visible(False)
    axes[0].legend(loc='lower right',fontsize=8)
    fig.suptitle('Lossless delta storage: complete denominators, all outcomes',fontsize=13)
    fig.savefig(output/'storage_outcomes.png',dpi=180);fig.savefig(output/'storage_outcomes.svg');plt.close(fig)
    svg=output/'storage_outcomes.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('originals',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=write(args.originals,args.output)
    print(json.dumps({k:result[k] for k in ('conditions','statuses','overall_vs_flat','overall_vs_solid','strong_local_control','primary_gate_passed')},indent=2))
