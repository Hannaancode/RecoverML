"""Prepare bounded payload pieces for authenticated GitHub connector uploads.

This does not contact GitHub or handle credentials. Publish the prepared tree
through the authorized connector and retain its returned commit SHA separately.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


def prepare(output, paths):
    output.mkdir(parents=True,exist_ok=False)
    files=[]
    piece_count=0
    for name in sorted(set(paths)):
        path=Path(name)
        if not path.is_file():raise ValueError('Missing checkpoint file: '+name)
        raw=path.read_bytes()
        try:
            content=raw.decode('utf-8');encoding='utf-8';limit=15000
        except UnicodeDecodeError:
            content=base64.b64encode(raw).decode('ascii');encoding='base64';limit=12000
        parts=[content[i:i+limit] for i in range(0,len(content),limit)] or ['']
        offsets=[]
        for index,part in enumerate(parts):
            fn=f'piece_{piece_count:05d}.json'
            (output/fn).write_text(json.dumps(dict(path=name,index=index,encoding=encoding,content=part)))
            offsets.append(fn);piece_count+=1
        mode='100755' if path.stat().st_mode & 0o111 else '100644'
        files.append(dict(path=name,mode=mode,encoding=encoding,pieces=offsets,
                          bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                          git_sha1=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()))
    manifest=dict(schema=1,local_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  files=files,pieces=piece_count)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(output=str(output),files=len(files),pieces=piece_count,
                total_bytes=sum(f['bytes'] for f in files))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--paths-from',type=Path)
    p.add_argument('paths',nargs='*')
    a=p.parse_args()
    names=a.paths + (json.loads(a.paths_from.read_text()) if a.paths_from else [])
    print(json.dumps(prepare(a.output,names)))
