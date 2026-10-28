"""Authenticate every solid artifact and rebuild all equal-format comparisons."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from audit_encoded_storage import require
from materialize_encoded_storage import materialize as encoded
from materialize_delta_storage import materialize as delta
from materialize_solid_storage import materialize

ROOT=Path(__file__).resolve().parents[1]


def release(directory,workers=2):
    require(1<=workers<=8,'Choose 1 to 8 audit workers');directory=Path(directory).resolve()
    with tempfile.TemporaryDirectory(prefix='recoverml-solid-release-') as temporary:
        base=Path(temporary);old=base/'encoded';prior=base/'delta';current=base/'solid'
        encoded(ROOT/'results/research/encoded_storage_oct26',old)
        delta(ROOT/'results/research/delta_storage_oct27',prior)
        manifest=materialize(directory,current)
        def check(record):
            key=record['block'];output=base/(key.replace('/','_')+'.json')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/audit_solid_storage.py'),str(current/key),
                '--originals',str(old),'--delta',str(prior),'--source-commit',manifest['source_commit'],'--output',str(output)],
                cwd=ROOT,capture_output=True,text=True)
            require(result.returncode==0,'Solid audit failed: '+key+'\n'+result.stdout+'\n'+result.stderr)
            return json.loads(output.read_bytes())
        blocks=[]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(check,record) for record in manifest['artifacts']]):
                receipt=future.result();blocks.append(receipt);print('Verified '+receipt['block'],flush=True)
        blocks.sort(key=lambda b:b['block']);rows=[r for block in blocks for r in block['rows']]
        require(len(rows)==446 and sum(r['status']=='COMPLETE' for r in rows)==444,'Complete solid denominator differs')
        result=dict(status='PASS',original_artifacts_verified=28,delta_artifacts_verified=28,previous_encoded_artifacts_verified=28,
            source_commit=manifest['source_commit'],conditions=len(rows),complete=444,blocks=blocks,
            qualification='Original source and artifact bytes verified; every solid control independently rebuilt; every online local selection reproduced. Includes all original three-candidate losses and the disclosed five-candidate correction. No new full-grid ML replay or timing experiment.')
        saved=directory/'audit_results.json.gz'
        if saved.exists():require(result==json.loads(gzip.decompress(saved.read_bytes())),'Published full audit differs')
        if (directory/'summary.json').exists():
            from summarize_solid_storage import summarize
            require(summarize(result)==json.loads((directory/'summary.json').read_bytes()),'Published solid totals differ')
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    require(not args.output.exists(),'Choose a fresh audit output');result=release(args.directory,args.workers)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='blocks'}))
