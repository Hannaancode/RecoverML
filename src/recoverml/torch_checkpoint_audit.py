"""Export and independently load native .pt state_dicts from audited captures."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from .core import Graph,canonical,pack,unpack
from .operators import execute


def run(benchmark,out):
    import torch
    out.mkdir(parents=True,exist_ok=False);(out/'checkpoints').mkdir()
    rows=[];data=[]
    with threadpool_limits(limits=1):
        for history in json.loads((benchmark/'histories.json').read_text()):
            case=history['case_id'];archive=benchmark/'capture_archives'/case
            g=Graph.read(archive/'manifest.json')
            info=json.loads((archive/'capture_info.json').read_text())
            data.append(dict(case_id=case,**info['dataset_provenance'],
                             version_accuracy=info['version_accuracy']))
            for version,targets in g.targets.items():
                model_id,pred_id=targets
                original=unpack((archive/'blobs'/(g.nodes[model_id].blob+'.pkl')).read_bytes())
                native=dict(params=original['params'],architecture=original['architecture'],
                    state_dict={k:torch.from_numpy(v.copy()) for k,v in original['state'].items()})
                path=out/'checkpoints'/f'{case}-v{version}.pt';torch.save(native,path)
                loaded=torch.load(path,map_location='cpu',weights_only=True)
                recovered=dict(recoverml_checkpoint=1,params=loaded['params'],architecture=loaded['architecture'],
                    state={k:np.array(v.numpy(),copy=True) for k,v in sorted(loaded['state_dict'].items())})
                weights_exact=pack(recovered)==pack(original)
                feature_id=g.nodes[model_id].deps[0];split_id=g.nodes[model_id].deps[2]
                features=unpack((archive/'blobs'/(g.nodes[feature_id].blob+'.pkl')).read_bytes())
                split=unpack((archive/'blobs'/(g.nodes[split_id].blob+'.pkl')).read_bytes())
                pred=execute('torch_predict',[recovered,features,split],{})
                prediction_exact=hashlib.sha256(pack(pred)).hexdigest()==g.nodes[pred_id].blob
                if not weights_exact or not prediction_exact:raise RuntimeError('native checkpoint mismatch')
                accuracy=next(s for s in info['version_accuracy'] if str(s['version'])==version)
                rows.append(dict(case_id=case,version=version,architecture=original['architecture'],
                    weights_exact=weights_exact,predictions_exact=prediction_exact,
                    captured_artifact_sha256=g.nodes[model_id].blob,
                    checkpoint_path=str(path.relative_to(out)),file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    parameters=accuracy['parameters'],test_accuracy=accuracy['accuracy']))
    with (out/'checkpoint_verification.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'dataset_provenance.json').write_bytes(canonical(data))
    report=dict(checkpoints=len(rows),all_weights_exact=True,all_predictions_exact=True,
        torch_version=torch.__version__,weights_only=True,device='cpu',
        scope='Trained weight state and inference; excludes optimizer state and training-resume semantics')
    (out/'summary.json').write_bytes(canonical(report))
    hashes={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.rglob('*') if p.is_file()}
    (out/'HASHES.json').write_bytes(canonical(hashes));return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--benchmark',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    print(json.dumps(run(args.benchmark,args.out),indent=2))

if __name__=='__main__':main()
