import hashlib,io,json,lzma,re,sys,tarfile,time,zlib
from pathlib import Path
from recoverml.encoded_store import encode,decode
from recoverml.core import canonical,digest

base=Path('work/encoded_all_originals/transfer/scientific')
rows=json.loads((base/'conditions.json').read_bytes())
inventory=json.loads((base/'payload_inventory.json').read_bytes())
with tarfile.open(base/'objects.tar.gz') as t:
    objects={m.name[:-4]:t.extractfile(m).read() for m in t if m.isfile()}
assert all(digest(v)==k for k,v in objects.items())
raw={b:decode(objects[x['adaptive']['object']],x['raw_bytes'],b) for b,x in inventory.items()}
encoded_chunks={}; recipes={}
for b,data in raw.items():
    stops=sorted({0,len(data)}|{m.start() for m in re.finditer(rb'\{"class":"DecisionTreeClassifier",|\{"classes":',data)}) if data.startswith(b'RECOVERML-MODEL-V1\n') else [0,len(data)]
    parts=[data[a:z] for a,z in zip(stops,stops[1:])]
    assert b''.join(parts)==data
    ids=[]
    for p in parts:
        sha=digest(p);ids.append([sha,len(p)])
        if sha not in encoded_chunks:encoded_chunks[sha]=encode(p)
    recipes[b]=ids
results=[];cache={}
for row in rows:
    for method in ['adaptive_exact','adaptive_snapshots']:
        selected=row['methods'][method]['selected'];meta=objects[row['methods'][method]['metadata_object']]
        index=canonical(dict(metadata=meta.hex(),recipes={b:recipes[b] for b in selected}))
        chunks={sha for b in selected for sha,n in recipes[b]}
        shared=48+len(encode(index))+sum(len(encoded_chunks[s]) for s in chunks)
        key=(row['methods'][method]['metadata_object'],tuple(selected))
        if key not in cache:
            # Canonical index retains every pathname, size and original checksum.
            files=[('metadata.rml',meta)]+[('blobs/'+b+'.pkl',raw[b]) for b in sorted(selected)]
            index=canonical([[name,len(data),digest(data)] for name,data in files])
            payload=len(index).to_bytes(8,'big')+index+b''.join(data for name,data in files)
            packed=encode(payload)
            assert decode(packed,len(payload),digest(payload))==payload
            bio=io.BytesIO()
            with tarfile.open(fileobj=bio,mode='w',format=tarfile.USTAR_FORMAT) as t:
                for name,data in files:
                    ti=tarfile.TarInfo(name);ti.size=len(data);t.addfile(ti,io.BytesIO(data))
            tarxz=len(lzma.compress(bio.getvalue(),preset=6))
            cache[key]=(48+len(packed),tarxz)
        solid,tarxz=cache[key]
        result=dict(case=row['case'],method=method,flat=row['methods'][method]['bytes'],shared=shared,solid=solid,tarxz=tarxz)
        results.append(result);print(json.dumps(result),flush=True)
Path('work/pilot_shared_oct27.json').write_text(json.dumps(results,indent=2)+'\n')
