"""Verify every original artifact and independently audit the complete recovery census."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from materialize_recovery_census import materialize,require
from audit_recovery_census import complete


def release(directory):
    with tempfile.TemporaryDirectory(prefix='recoverml-census-audit-') as temporary:
        target=Path(temporary)/'materialized'
        manifest=materialize(directory,target)
        result=complete(target)
        require(result['source_commit']==manifest['source_commit'],'Materialized source identity differs')
        for block in result['blocks']:
            path=target/block['dataset']/block['recipe']/'runner_audit.json'
            if path.exists():
                original=json.loads(path.read_bytes())
                require({k:v for k,v in original.items() if k!='auditor_sha256'}==
                        {k:v for k,v in block.items() if k!='auditor_sha256'},
                        'Recreated audit differs from original runner audit')
        receipt=json.loads((directory/'verification/receipt.json').read_bytes())
        archive=directory/'verification/corrected-audit-original.zip'
        require('sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['artifact']['digest'],
                'Original corrected cloud-audit artifact differs')
        with zipfile.ZipFile(archive) as zipped:
            require(zipped.namelist()==['complete_recovery_census_audit.json'],'Cloud audit inventory differs')
            require(json.loads(zipped.read(zipped.namelist()[0]))==result,
                    'Complete local audit differs from verification-only cloud audit')
        result['audit_repair']='Numeric version ordering corrected after initial runner audits failed; original timing artifacts unchanged.'
        result['original_artifacts_verified']=len(manifest['artifacts'])
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=release(args.directory)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('blocks',)},indent=2))
