"""Rebuild both original attempts and re-audit every final delta condition."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile

from audit_encoded_storage import require
from materialize_encoded_storage import materialize as previous
from materialize_delta_storage import materialize
from summarize_delta_storage import summarize
from strengthen_delta_local import complete as strengthen

ROOT=Path(__file__).resolve().parents[1]


def release(directory,workers=2):
    require(1<=workers<=8,'Choose 1 to 8 audit processes')
    directory=Path(directory).resolve()
    with tempfile.TemporaryDirectory(prefix='recoverml-delta-release-') as temporary:
        base=Path(temporary);old=base/'originals';final=base/'final';first=base/'first'
        previous(ROOT/'results/research/encoded_storage_oct26',old)
        manifest=materialize(directory,final);materialize(directory,first,'first')
        failures=[]
        for record in manifest['first']['artifacts']:
            p=first/record['block']
            if (p/'failure.txt').exists():failures.append(record['block'])
        require(set(failures)=={'primary/breast_cancer/pca_neighbors','primary/digits/pca_neighbors'},'First-attempt failures differ')
        def check(record):
            key=record['block'];path=final/key;output=base/('audit_'+key.replace('/','_')+'.json')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/audit_delta_storage.py'),str(path),
                '--originals',str(old),'--output',str(output)],cwd=ROOT,capture_output=True,text=True)
            require(result.returncode==0,'Delta block audit failed: '+key+'\n'+result.stdout+'\n'+result.stderr)
            receipt=json.loads(output.read_bytes())
            require(receipt==json.loads((path/'runner_audit.json').read_bytes()),'Saved/cloud/local audit differs: '+key)
            return receipt
        audited=[]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(check,record) for record in manifest['final']['artifacts']]
            for future in as_completed(futures):
                receipt=future.result();audited.append(receipt);print('Verified '+receipt['block'],flush=True)
        strong=json.loads(gzip.decompress((directory/'strengthened_local.json.gz').read_bytes()))
        strengthen(old,final,strong)
        summary,rows=summarize(final,strong)
        require(summary==json.loads((directory/'summary.json').read_bytes()),'Published aggregate differs from complete grid')
        return dict(status='PASS',original_artifacts_verified=56,previous_original_artifacts_verified=28,
            first_attempt_failures=sorted(failures),final_source_commit=manifest['final']['source_commit'],
            final_conditions=len(rows),final_blocks=sorted(audited,key=lambda r:r['block']),
            primary_gate_passed=summary['primary_gate_passed'],
            qualification='Original artifact bytes, full denominators, independent exact objectives, selected file reconstruction and all published totals reconciled. No new model replay or timing experiment.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();result=release(args.directory,args.workers);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='final_blocks'},indent=2))
