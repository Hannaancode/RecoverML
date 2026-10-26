"""Restore byte-identical recovery-census GitHub artifacts from checked ZIP parts."""
import argparse
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import stat
import zipfile


def require(ok,message):
    if not ok:raise ValueError(message)


def safe(name):
    p=PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and ':' not in name and '\\' not in name,
            'Unsafe evidence path')
    return p


def materialize(directory,output):
    directory,output=Path(directory).resolve(),Path(output).resolve()
    require(not output.exists(),'Choose a fresh output directory')
    manifest=json.loads((directory/'artifact_manifest.json').read_bytes())
    config=json.loads((Path(__file__).resolve().parents[1]/'configs/recovery_census_oct26.json').read_bytes())
    require(manifest['datasets']==config['datasets'] and manifest['recipes']==config['recipes'],
            'Frozen catalogue differs')
    expected={(d,r) for d in manifest['datasets'] for r in manifest['recipes']}
    records=manifest['artifacts']
    require(len(records)==len(expected) and {(r['dataset'],r['recipe']) for r in records}==expected,
            'All fixed dataset/recipe artifacts required')
    for record in records:
        parts=[];seen=set()
        for item in record['parts']:
            path=safe(item['path'])
            require(str(path) not in seen,'Duplicate transport part')
            seen.add(str(path))
            resolved=(directory/path).resolve()
            require(resolved.is_relative_to(directory),'Transport part leaves evidence directory')
            raw=resolved.read_bytes()
            require(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],'Part hash/size differs')
            parts.append(raw)
        raw=b''.join(parts)
        require('sha256:'+hashlib.sha256(raw).hexdigest()==record['artifact']['digest'],'Original artifact ZIP digest differs')
        require(record['artifact']['workflow_run']['head_sha']==manifest['source_commit'],'Artifact source differs')
        require(record['artifact']['name']=='recovery-census-'+record['dataset']+'-'+record['recipe'],
                'Artifact group identity differs')
        destination=output/record['dataset']/record['recipe']
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=archive.namelist()
            require(len(names)==len(set(names)) and set(names)==set(record['files']),'ZIP member inventory differs')
            seen_targets=set()
            for info in archive.infolist():
                p=safe(info.filename)
                require(not info.is_dir() and not stat.S_ISLNK(info.external_attr>>16),'Regular artifact files required')
                content=archive.read(info)
                expected_file=record['files'][info.filename]
                require(len(content)==expected_file['bytes'] and hashlib.sha256(content).hexdigest()==expected_file['sha256'],
                        'Original member differs')
                if p.parts[0]=='census':
                    target=destination.joinpath(*p.parts[1:])
                elif info.filename=='census_audit.json':
                    target=destination/'runner_audit.json'
                else:
                    raise ValueError('Unexpected census artifact prefix')
                require(target.resolve().is_relative_to(destination.resolve()),'Member leaves output block')
                require(target.resolve() not in seen_targets,'Duplicate normalized output member')
                seen_targets.add(target.resolve())
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(content)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();manifest=materialize(args.directory,args.output)
    print(json.dumps(dict(status='PASS',artifacts=len(manifest['artifacts']),source_commit=manifest['source_commit'])))
