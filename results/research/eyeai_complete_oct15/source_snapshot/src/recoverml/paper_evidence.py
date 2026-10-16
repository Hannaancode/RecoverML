"""Regenerate manuscript tables and cluster-aware statistics from raw evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .core import canonical
from .benchmark import write_csv


def read_csv(path):
    with path.open() as handle:return list(csv.DictReader(handle))


def cluster_interval(rows):
    repeats=sorted({r['repeat'] for r in rows})
    # A seed occurs at all widths so resample whole seed blocks together.
    blocks=np.array([[float(r['speedup_v2_v4']) for r in rows if r['repeat']==repeat]
                     for repeat in repeats])
    rng=np.random.default_rng(2213)
    indexes=rng.integers(len(blocks),size=(10000,len(blocks)))
    estimates=np.median(blocks[indexes].reshape(10000,-1),axis=1)
    return np.percentile(estimates,[2.5,97.5]).tolist()


def run(root,out):
    out.mkdir(parents=True,exist_ok=False)
    results=root/'results'/'milestone2'
    controls=read_csv(results/'boundary_controls_oct13'/'history_medians.csv')
    control_table=[]
    for mode in ('none','mixed','all'):
        rows=[r for r in controls if r['mode']==mode];ci=cluster_interval(rows)
        control_table.append(dict(boundary_mode=mode,histories=len(rows),seed_blocks=5,
            median_speedup=float(np.median([float(r['speedup_v2_v4']) for r in rows])),
            cluster_bootstrap_low=ci[0],cluster_bootstrap_high=ci[1],
            median_variable_reduction=float(np.median([1-float(r['v4_variables'])/float(r['v2_variables']) for r in rows]))))
    write_csv(out/'boundary_control_statistics.csv',control_table)
    neural=read_csv(results/'pytorch_validated_oct13'/'raw_requests.csv')
    table=[]
    for budget in sorted({float(r['budget_fraction']) for r in neural}):
        for policy in sorted({r['policy'] for r in neural}):
            rows=[r for r in neural if r['policy']==policy and float(r['budget_fraction'])==budget]
            good=[r for r in rows if r['exact'].lower()=='true']
            table.append(dict(budget_fraction=budget,policy=policy,requests=len(rows),
                exact=len(good),budget_blocked=sum(r['within_budget'].lower()!='true' for r in rows),
                restore_failed=sum(r['status']=='restore_failed' for r in rows)))
    write_csv(out/'pytorch_coverage.csv',table)
    checkpoints=read_csv(results/'pytorch_validated_checkpoints_oct13'/'checkpoint_verification.csv')
    quality=[]
    for architecture in ('cnn','text_transformer'):
        rows=[r for r in checkpoints if r['architecture']==architecture]
        values=[float(r['test_accuracy']) for r in rows]
        quality.append(dict(architecture=architecture,models=len(rows),
            parameters=int(rows[0]['parameters']),median_test_accuracy=float(np.median(values)),
            min_test_accuracy=min(values),max_test_accuracy=max(values)))
    write_csv(out/'model_quality.csv',quality)
    oracle=json.loads((results/'oracle_oct13'/'summary.json').read_text())
    claims=dict(pytorch_requests=len(neural),pytorch_histories=len({r['case_id'] for r in neural}),
        v4_admitted=sum(r['within_budget'].lower()=='true' for r in neural if r['policy']=='recoverability_v4'),
        v4_exact=sum(r['exact'].lower()=='true' for r in neural if r['policy']=='recoverability_v4'),
        native_checkpoints=len(checkpoints),boundary_controls=control_table,
        oracle=oracle,quality=quality,
        limitations=['One measured CPU machine','No GPU or pretrained large model claim',
                     'No timing comparison against original HELIX Kishu or ExoFlow implementations',
                     'Novelty not independently reviewed','No target venue selected'])
    (out/'claims.json').write_bytes(canonical(claims))
    sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('src/recoverml','configs') for p in (root/folder).glob('*') if p.is_file()}
    (out/'source_hashes.json').write_bytes(canonical(sources))
    inputs=[results/'boundary_controls_oct13'/'history_medians.csv',
            results/'pytorch_validated_oct13'/'raw_requests.csv',
            results/'pytorch_validated_checkpoints_oct13'/'checkpoint_verification.csv',
            results/'oracle_oct13'/'summary.json']
    (out/'input_hashes.json').write_bytes(canonical({str(p.relative_to(root)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}))
    return claims


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[2],args.out),indent=2))

if __name__=='__main__':main()
