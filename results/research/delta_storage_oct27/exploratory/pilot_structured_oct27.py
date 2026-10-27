import base64,json,re,tarfile
from pathlib import Path
from recoverml.encoded_store import encode,decode,shuffle,unshuffle
from recoverml.core import digest
base=Path('work/encoded_all_originals/transfer/scientific')
inventory=json.loads((base/'payload_inventory.json').read_bytes())
with tarfile.open(base/'objects.tar.gz') as t:objects={m.name[:-4]:t.extractfile(m).read() for m in t if m.isfile()}
records=[]
for blob,item in inventory.items():
    encoded=objects[item['adaptive']['object']];raw=decode(encoded,item['raw_bytes'],blob)
    if not raw.startswith(b'RECOVERML-MODEL-V1\n'):continue
    segments=[];pos=0;count=0
    for match in re.finditer(rb'(?<="data":")[A-Za-z0-9+/]{96,}={0,2}(?=")',raw):
        data=base64.b64decode(match.group(),validate=True)
        if base64.b64encode(data)!=match.group():continue
        gap=raw[pos:match.start()];segments += [b'\0'+len(gap).to_bytes(8,'big')+gap,b'\1'+len(data).to_bytes(8,'big')+shuffle(data)]
        pos=match.end();count+=1
    gap=raw[pos:];segments.append(b'\0'+len(gap).to_bytes(8,'big')+gap)
    transformed=b''.join(segments);assert len(transformed)<=len(raw)+9
    cooked=encode(transformed);new=41+len(cooked)
    records.append(dict(blob=blob,raw=len(raw),old=len(encoded),structured=new,arrays=count,saving=1-new/len(encoded)))
    print(json.dumps(records[-1]),flush=True)
Path('work/pilot_structured_oct27.json').write_text(json.dumps(records,indent=2)+'\n')
