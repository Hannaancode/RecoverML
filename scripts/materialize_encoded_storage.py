"""Restore every original storage-study artifact from checked transport parts."""
import argparse
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import stat
import zipfile

from audit_encoded_storage import require

ROOT=Path(__file__).resolve().parents[1]


def safe(name):
    path=PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name,'Unsafe transport path')
    return path


def materialize(directory,output):
    directory,output=Path(directory).resolve(),Path(output).resolve()
    require(not output.exists(),'Choose a fresh materialization directory')
    manifest=json.loads((directory/'artifact_manifest.json').read_bytes())
    config=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    transfer=json.loads((ROOT/'configs/encoded_storage_transfer_oct26.json').read_bytes())
    require(manifest['datasets']==config['datasets'] and manifest['recipes']==config['recipes'] and
            manifest['transfer_groups']==transfer['groups'],'Fixed catalogue differs')
    records=manifest['artifacts']
    primary={(d,r) for d in config['datasets'] for r in config['recipes']}
    require(len(records)==len(primary)+len(transfer['groups']),'Every original artifact is required')
    require({(r['dataset'],r['recipe']) for r in records if r['kind']=='primary'}==primary and
            {r['group'] for r in records if r['kind']=='transfer'}==set(transfer['groups']),'Missing or replaced artifact group')
    seen_groups=set()
    for record in records:
        if record['kind']=='primary':
            key=('primary',record['dataset'],record['recipe']);destination=output/'primary'/record['dataset']/record['recipe']
            name='encoded-storage-'+record['dataset']+'-'+record['recipe'];prefix='encoded_census';audit='encoded_census_audit.json'
            source=manifest['primary_source_commit']
        elif record['kind']=='transfer':
            key=('transfer',record['group']);destination=output/'transfer'/record['group']
            name='encoded-transfer-'+record['group'];prefix='encoded_transfer';audit='encoded_transfer_audit.json'
            source=manifest['transfer_source_commit']
        else:raise ValueError('Unknown artifact scope')
        require(key not in seen_groups,'Duplicate artifact group');seen_groups.add(key)
        require(record['artifact']['name']==name and record['artifact']['workflow_run']['head_sha']==source,'Artifact/source identity differs')
        parts=[];seen=set()
        for part in record['parts']:
            path=safe(part['path']);resolved=(directory/path).resolve()
            require(resolved.is_relative_to(directory) and resolved not in seen,'Unsafe or duplicate part');seen.add(resolved)
            raw=resolved.read_bytes()
            require(len(raw)==part['bytes'] and hashlib.sha256(raw).hexdigest()==part['sha256'],'Part hash/size differs')
            parts.append(raw)
        raw=b''.join(parts)
        require('sha256:'+hashlib.sha256(raw).hexdigest()==record['artifact']['digest'],'Original artifact ZIP digest differs')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=archive.namelist();require(len(names)==len(set(names)) and set(names)==set(record['files']),'ZIP member inventory differs')
            destinations=set()
            for info in archive.infolist():
                path=safe(info.filename)
                require(not info.is_dir() and not stat.S_ISLNK(info.external_attr>>16),'Regular ZIP members required')
                content=archive.read(info);identity=record['files'][info.filename]
                require(len(content)==identity['bytes'] and hashlib.sha256(content).hexdigest()==identity['sha256'],'Original artifact member differs')
                if path.parts[0]==prefix:target=destination.joinpath(*path.parts[1:])
                elif info.filename==audit:target=destination/'runner_audit.json'
                else:raise ValueError('Unexpected artifact prefix')
                resolved=target.resolve();require(resolved.is_relative_to(destination.resolve()) and resolved not in destinations,'Duplicate or unsafe output member')
                destinations.add(resolved);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=materialize(args.directory,args.output);print(json.dumps(dict(status='PASS',original_artifacts=len(result['artifacts']))))
