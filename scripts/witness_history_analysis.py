"""Compare storage savings for matched short and long pipeline histories."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def analyze(short,long,output):
    output.mkdir(parents=True,exist_ok=False)
    def read(path):
        with path.open() as stream:
            return {r['case']:r for r in csv.DictReader(stream)}
    a,b=read(short/'summary.csv'),read(long/'summary.csv')
    common=sorted(set(a)&set(b))
    if not common: raise ValueError('No matching cases')
    result=[]
    for name in ('breast_cancer','iris','wine'):
        cases=[c for c in common if a[c]['dataset']==name and
               a[c]['observed_exact_feature_witness']=='True' and
               b[c]['observed_exact_feature_witness']=='True']
        if not cases: raise ValueError('No matching lossless cases for '+name)
        def saving(rows):
            return float(np.mean([100*int(rows[c]['saved_bytes'])/int(rows[c]['logical_bytes']) for c in cases]))
        result.append(dict(dataset=name,matched_cases=len(cases),
                           short_mean_saving_percent=saving(a),long_mean_saving_percent=saving(b)))
    cpu=[]
    for experiment in (short,long):
        traces=json.loads((experiment/'execution_traces.json').read_text())
        cases=read(experiment/'summary.csv')
        for name in ('breast_cancer','iris','wine'):
            for policy in ('logical','witness'):
                values=[r['cpu_s']*1000 for r in traces if r['policy']==policy and
                    cases[r['case']]['dataset']==name and
                    cases[r['case']]['observed_exact_feature_witness']=='True']
                cpu.append(dict(experiment=experiment.name,dataset=name,policy=policy,
                    requests=len(values),median_recorded_cpu_ms=float(np.median(values))))
    hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest()
            for base in (short,long) for path in (base/'summary.csv',base/'execution_traces.json')}
    report=dict(storage_comparison=result,descriptive_cpu=cpu,input_sha256=hashes,
        qualification='Matched split seeds and lossless formats within three datasets; no latency speedup or population confidence claim',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(7,4));xs=np.arange(len(result))
    ax.bar(xs-.18,[r['short_mean_saving_percent'] for r in result],width=.36,label='3 model versions')
    ax.bar(xs+.18,[r['long_mean_saving_percent'] for r in result],width=.36,label='12 model versions')
    ax.set_xticks(xs,[r['dataset'].replace('_',' ') for r in result])
    ax.set_ylabel('Total stored bytes saved (%)');ax.set_title('Matched histories with lossless imported features')
    ax.legend();fig.tight_layout();fig.savefig(output/'history_length_storage.png',dpi=180);plt.close(fig)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--short',type=Path,required=True)
    parser.add_argument('--long',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(analyze(args.short,args.long,args.output),indent=2))
