"""Rebuild and audit all fresh and frozen encoded-storage artifacts and controls."""
import argparse
import gzip
import json
from pathlib import Path
import tempfile

from materialize_encoded_storage import materialize
from audit_encoded_storage import complete,require
from audit_encoded_transfer import block as transfer_block
from strengthen_encoded_gzip import primary as stronger_primary,transfer as stronger_transfer


def release(directory):
    directory=Path(directory)
    published=json.loads(gzip.decompress((directory/'strengthened_gzip.json.gz').read_bytes()))
    with tempfile.TemporaryDirectory(prefix='recoverml-storage-release-') as temporary:
        target=Path(temporary)/'originals';manifest=materialize(directory,target)
        primary=complete(target/'primary')
        require(primary['source_commit']==manifest['primary_source_commit'],'Fresh source identity differs')
        stronger={};transfers={};stronger_frozen={}
        for block in primary['blocks']:
            key=block['dataset']+'/'+block['recipe'];path=target/'primary'/block['dataset']/block['recipe']
            require(json.loads((path/'runner_audit.json').read_bytes())==block,'Fresh runner/local audits differ')
            stronger[key]=stronger_primary(path,published['primary'][key])
        for group in manifest['transfer_groups']:
            path=target/'transfer'/group;result=transfer_block(path)
            require(result['source_commit']==manifest['transfer_source_commit'],'Frozen source identity differs')
            require(json.loads((path/'runner_audit.json').read_bytes())==result,'Transfer runner/local audits differ')
            transfers[group]={k:v for k,v in result.items() if k!='conditions_detail'}
            stronger_frozen[group]=stronger_transfer(path,published['transfer'][group])
    def compact(value):
        return dict({k:v for k,v in value.items() if k!='comparisons'},comparisons=[
            {k:v for k,v in row.items() if k in ('case','strong_gzip_bytes','adaptive_bytes','saving')}
            for row in value['comparisons']])
    return dict(status='PASS',original_artifacts_verified=len(manifest['artifacts']),primary=primary,
        transfer=transfers,strengthened_gzip=dict(primary={k:compact(v) for k,v in stronger.items()},
                                               transfer={k:compact(v) for k,v in stronger_frozen.items()}),
        qualification='All original bytes and full denominators reconciled. Stronger gzip is a disclosed post-hoc byte control, not additional model replay. Equal-codec manual optima still tie.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=release(args.directory)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=result['status'],original_artifacts_verified=result['original_artifacts_verified'],
        primary_conditions=result['primary']['conditions'],primary_requests=result['primary']['requests'],
        robust_requests=result['primary']['robust_requests'],robust_exact=result['primary']['robust_exact'],
        unexpected=result['primary']['unexpected'],transfer_conditions=sum(r['conditions'] for r in result['transfer'].values())),indent=2))
