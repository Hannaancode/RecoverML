"""Summarize every verified solid condition, including the original losses."""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import json
from pathlib import Path
import statistics


def comparison(rows,baseline,ours='production_bytes'):
    complete=[r for r in rows if r['status']=='COMPLETE'];gains=[1-r[ours]/r[baseline] for r in complete]
    best=max(complete,key=lambda r:1-r[ours]/r[baseline]) if complete else None
    return dict(wins=sum(r[ours]<r[baseline] for r in complete),ties=sum(r[ours]==r[baseline] for r in complete),
        losses=sum(r[ours]>r[baseline] for r in complete),unmeasured=len(rows)-len(complete),
        at_least_ten_percent=sum(g>=.1 for g in gains),median_saving=statistics.median(gains) if gains else None,
        maximum=None if best is None else dict(case=best['case'],block=best['block'],production_bytes=best[ours],comparison_bytes=best[baseline],saving=1-best[ours]/best[baseline]))


def summarize(audit):
    rows=[dict(block=b['block'],**r) for b in audit['blocks'] for r in b['rows']]
    comparisons={'previous_flat':'previous_flat_bytes','previous_delta':'previous_delta_bytes',
                 'solid_control':'solid_control_bytes','equal_format_local':'equal_format_local_bytes'}
    groups={key:[r for r in rows if ('primary' if r['block'].startswith('primary/') else r['block'].split('/')[1])==key]
            for key in ('primary','scientific','cloud','retinal','letter')}
    strata=defaultdict(list)
    for row in groups['primary']:
        dataset,recipe,version,loss=row['case'].split('/')
        strata[dataset+'/'+recipe+'/'+loss].append(row)
    gates={key:dict(conditions=len(values),at_least_ten_percent=sum(r['status']=='COMPLETE' and 1-r['production_bytes']/r['previous_flat_bytes']>=.1 for r in values)) for key,values in sorted(strata.items())}
    for gate in gates.values():gate['passed']=gate['conditions']==3 and gate['at_least_ten_percent']/gate['conditions']>=.9
    return dict(conditions=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
        comparisons={name:comparison(rows,field) for name,field in comparisons.items()},
        groups={key:dict(conditions=len(group),comparisons={name:comparison(group,field) for name,field in comparisons.items()}) for key,group in groups.items()},
        formats=dict(Counter(r['production_format'] for r in rows if r['status']=='COMPLETE')),
        original_three_candidate_vs_equal_format_local=comparison(rows,'equal_format_local_bytes','three_candidate_bytes'),
        corrected_cases=[dict(case=r['case'],block=r['block'],before=r['three_candidate_bytes'],after=r['production_bytes'],selected_format=r['production_format']) for r in rows if r['status']=='COMPLETE' and r['production_bytes']<r['three_candidate_bytes']],
        selected_file_hash_checks=sum(b['selected_file_checks'] for b in audit['blocks']),
        recorded_retained_target_exports_reconciled=sum(b['retained_target_export_checks'] for b in audit['blocks']),
        primary_strata=gates,primary_strata_passed=sum(g['passed'] for g in gates.values()),primary_gate_passed=all(g['passed'] for g in gates.values()),
        qualification='Post-hoc five-candidate storage choice on the entire reused catalogue; all three original equal-format local losses preserved. Repeated artifacts/conditions are not independent production samples. No new full-grid ML replay, timing, memory benchmark, or joint-compression optimum.')


def write(audit,directory):
    directory=Path(directory);summary=summarize(audit)
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    rows=[dict(block=b['block'],**r) for b in audit['blocks'] for r in b['rows']]
    fields=['block','case','status','production_format','production_bytes','previous_flat_bytes','previous_delta_bytes',
            'three_candidate_bytes','equal_format_local_bytes','solid_control_bytes']
    with (directory/'all_conditions.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=['Previous flat optimum','Previous flat/delta choice','Solid archive control','Local search with all formats','Original three-candidate choice\nvs local search with all formats']
    values=list(summary['comparisons'].values())+[summary['original_three_candidate_vs_equal_format_local']]
    fig,ax=plt.subplots(figsize=(10.5,4.8));left=[0]*5
    for key,color,label in [('wins','#197b62','Smaller'),('ties','#a8b5bd','Equal'),('losses','#d98531','Larger'),('unmeasured','#aa5670','Unmeasured')]:
        counts=[v[key] for v in values];ax.barh(names,counts,left=left,color=color,label=label,height=.65)
        for i,count in enumerate(counts):
            if count>=10:ax.text(left[i]+count/2,i,str(count),ha='center',va='center',fontsize=10)
        left=[n+c for n,c in zip(left,counts)]
    ax.invert_yaxis();ax.set_xlim(0,446);ax.set_xlabel('All 446 fixed conditions');ax.spines[['top','right']].set_visible(False)
    ax.set_title('Storage outcomes: full denominator and original losses',pad=14)
    ax.legend(loc='lower center',bbox_to_anchor=(.5,-.3),ncol=4,frameon=False)
    fig.text(.37,.035,'Each row includes 2 unmeasured conditions. The original three-candidate row includes 3 losses.',fontsize=8)
    fig.subplots_adjust(left=.36,bottom=.23,top=.89,right=.98)
    fig.savefig(directory/'storage_outcomes.png',dpi=180);fig.savefig(directory/'storage_outcomes.svg');plt.close(fig)
    svg=directory/'storage_outcomes.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('audit',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raw=args.audit.read_bytes();audit=json.loads(gzip.decompress(raw) if args.audit.suffix=='.gz' else raw)
    result=write(audit,args.output);print(json.dumps({k:result[k] for k in ('conditions','comparisons','corrected_cases','primary_strata_passed')},indent=2))
