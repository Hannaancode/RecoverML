"""Authenticate and restore all original source-pinned solid-study artifacts."""
import argparse
import io
import json
from pathlib import Path
import zipfile

from audit_encoded_storage import require
from materialize_encoded_storage import safe
from recoverml.core import digest

ROOT=Path(__file__).resolve().parents[1]
MEMBERS={'commit.txt','packages.txt','execution.log','platform.txt','result.json','source_snapshot.tar.gz'}


def materialize(directory,output):
    directory,output=Path(directory).resolve(),Path(output).resolve()
    require(not output.exists(),'Choose a fresh solid materialization directory')
    manifest=json.loads((directory/'artifact_manifest.json').read_bytes())
    config=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    expected={'primary/'+d+'/'+r for d in config['datasets'] for r in config['recipes']}|{'transfer/'+g for g in ('scientific','cloud','retinal','letter')}
    records=manifest['artifacts']
    require(len(records)==28 and {r['block'] for r in records}==expected,'Missing or repeated solid group')
    for record in records:
        require(record['artifact']['workflow_run']['head_sha']==manifest['source_commit'],'Solid artifact source differs')
        require(record['artifact']['workflow_run']['id']==manifest['workflow_run_id'],'Solid artifact run differs')
        path=(directory/safe(record['path'])).resolve();require(path.is_relative_to(directory),'Unsafe solid ZIP path')
        raw=path.read_bytes()
        require(len(raw)==record['bytes'] and digest(raw)==record['sha256'] and 'sha256:'+digest(raw)==record['artifact']['digest'],'Original solid ZIP differs')
        target=output/safe(record['block']);require(target.resolve().is_relative_to(output),'Unsafe solid output')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=archive.namelist()
            require(len(names)==len(set(names)) and set(names)==MEMBERS==set(record['files']),'Solid ZIP inventory differs')
            for name in sorted(names):
                data=archive.read(name);identity=record['files'][name]
                require(len(data)==identity['bytes'] and digest(data)==identity['sha256'],'Solid member differs')
                target.mkdir(parents=True,exist_ok=True);(target/name).write_bytes(data)
        require((target/'commit.txt').read_text().strip()==manifest['source_commit'],'Solid recorded commit differs')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=materialize(args.directory,args.output)
    print(json.dumps(dict(status='PASS',artifacts=len(result['artifacts']),source_commit=result['source_commit'])))
