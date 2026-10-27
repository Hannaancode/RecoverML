"""Restore exact original delta-study ZIPs and their authenticated members."""
import argparse
import io
import json
from pathlib import Path
import stat
import zipfile

from audit_encoded_storage import require
from materialize_encoded_storage import safe
from recoverml.core import digest

ROOT=Path(__file__).resolve().parents[1]


def materialize(directory,output,attempt='final'):
    directory,output=Path(directory).resolve(),Path(output).resolve()
    require(not output.exists(),'Choose a fresh delta materialization directory')
    manifest=json.loads((directory/'artifact_manifest.json').read_bytes());records=manifest[attempt]['artifacts']
    config=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    expected={'primary/'+d+'/'+r for d in config['datasets'] for r in config['recipes']}|{'transfer/'+g for g in ('scientific','cloud','retinal','letter')}
    require(len(records)==28 and {r['block'] for r in records}==expected,'Missing or replaced delta artifact group')
    for record in records:
        require(record['artifact']['workflow_run']['head_sha']==manifest[attempt]['source_commit'],'Delta artifact source differs')
        chunks=[];seen=set()
        for part in record['parts']:
            path=(directory/safe(part['path'])).resolve()
            require(path.is_relative_to(directory) and path not in seen,'Unsafe or repeated delta part');seen.add(path)
            raw=path.read_bytes();require(len(raw)==part['bytes'] and digest(raw)==part['sha256'],'Delta transport part differs');chunks.append(raw)
        raw=b''.join(chunks);require('sha256:'+digest(raw)==record['artifact']['digest'],'Original delta artifact ZIP differs')
        target=output/safe(record['block'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=archive.namelist();require(len(names)==len(set(names)) and set(names)==set(record['files']),'Delta ZIP inventory differs')
            seen=set()
            for item in archive.infolist():
                p=safe(item.filename);require(not item.is_dir() and not stat.S_ISLNK(item.external_attr>>16),'Regular delta members required')
                content=archive.read(item);identity=record['files'][item.filename]
                require(len(content)==identity['bytes'] and digest(content)==identity['sha256'],'Delta artifact member differs')
                if p.parts[0]=='delta':out=target.joinpath(*p.parts[1:])
                elif item.filename=='delta_audit.json':out=target/'runner_audit.json'
                else:raise ValueError('Unexpected delta artifact prefix')
                require(out.resolve().is_relative_to(target.resolve()) and out not in seen,'Duplicate or unsafe delta output');seen.add(out)
                out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(content)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--attempt',choices=['first','final'],default='final')
    args=parser.parse_args();result=materialize(args.directory,args.output,args.attempt)
    print(json.dumps(dict(status='PASS',attempt=args.attempt,original_artifacts=len(result[args.attempt]['artifacts']))))
