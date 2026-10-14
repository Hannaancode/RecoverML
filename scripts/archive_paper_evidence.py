"""Preserve reports and every selected store path with checked shared payloads."""
import argparse,gzip,hashlib,io,json,shutil,tarfile
from pathlib import Path

def sha(raw):return hashlib.sha256(raw).hexdigest()

def save(destination,runs):
    destination.mkdir(parents=True,exist_ok=True);index=destination/'evidence_inventory.json'
    inventory=json.loads(index.read_text()) if index.exists() else {}
    for group,run in runs.items():
        output=destination/group;output.mkdir(exist_ok=True);record=dict(source_run=str(run),files={})
        for p in sorted(run.iterdir()):
            if not p.is_file():continue
            target=output/p.name
            if target.exists() and target.read_bytes()!=p.read_bytes():raise RuntimeError('Refusing evidence overwrite')
            if not target.exists():shutil.copyfile(p,target)
            entry=dict(sha256=sha(target.read_bytes()))
            if p.suffix=='.gz':entry['uncompressed_sha256']=sha(gzip.decompress(target.read_bytes()))
            record['files'][p.name]=entry
        source=run/'stores';path=output/'stores.tar.gz'
        if source.exists():
            files=sorted(p for p in source.rglob('*') if p.is_file());seen={}
            if not path.exists():
                with path.open('wb') as stream,gzip.GzipFile(fileobj=stream,mode='wb',mtime=0) as zipped:
                    with tarfile.open(fileobj=zipped,mode='w') as archive:
                        for item in files:
                            raw=item.read_bytes();identity=sha(raw);name=str(item.relative_to(source));info=tarfile.TarInfo(name);info.mode=0o644
                            if identity in seen:info.type=tarfile.LNKTYPE;info.linkname=seen[identity];archive.addfile(info)
                            else:info.size=len(raw);archive.addfile(info,io.BytesIO(raw));seen[identity]=name
            with tarfile.open(path,'r:gz') as archive:
                if len(archive.getmembers())!=len(files):raise RuntimeError('Archive path mismatch')
                for item in files:
                    if archive.extractfile(str(item.relative_to(source))).read()!=item.read_bytes():raise RuntimeError('Archive bytes mismatch')
            record['files']['stores.tar.gz']=dict(sha256=sha(path.read_bytes()),paths=len(files),complete_bytes_verified=True)
        inventory[group]=record
    index.write_text(json.dumps(inventory,indent=2)+'\n');print(json.dumps(dict(saved=list(runs),verified=True)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);p.add_argument('--run',action='append',required=True);a=p.parse_args()
    save(a.destination,{g:Path(path) for g,path in (r.split('=',1) for r in a.run)})
