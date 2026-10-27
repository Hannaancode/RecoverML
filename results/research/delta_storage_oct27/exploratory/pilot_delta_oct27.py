import json,tarfile
from pathlib import Path
from recoverml.encoded_store import encode,decode
from recoverml.core import digest
base=Path('work/encoded_all_originals/transfer/scientific');inventory=json.loads((base/'payload_inventory.json').read_bytes())
with tarfile.open(base/'objects.tar.gz') as t:objects={m.name[:-4]:t.extractfile(m).read() for m in t if m.isfile()}
raw={b:decode(objects[x['adaptive']['object']],x['raw_bytes'],b) for b,x in inventory.items()}
def common(a,b):
    lo,hi=0,min(len(a),len(b))
    while lo<hi:
        mid=(lo+hi+1)//2
        if a[:mid]==b[:mid]:lo=mid
        else:hi=mid-1
    return lo
records=[];seen=[]
for blob in sorted(raw,key=lambda b:(len(raw[b]),b)):
    data=raw[blob]
    if not data.startswith(b'RECOVERML-MODEL-V1\n'):continue
    best=None; choices=[]
    for other in seen:
        previous=raw[other];prefix=common(data,previous)
        suffix=common(data[prefix:][::-1],previous[prefix:][::-1])
        if prefix+suffix<128:continue
        choices.append((prefix+suffix,other,prefix,suffix))
    if choices:
        _,other,prefix,suffix=max(choices)
        previous=raw[other];middle=data[prefix:len(data)-suffix if suffix else len(data)]
        encoded=encode(middle)
        assert previous[:prefix]+middle+(previous[len(previous)-suffix:] if suffix else b'')==data
        best=dict(blob=blob,base=other,prefix=prefix,suffix=suffix,middle=len(middle),delta=len(encoded)+16,full=inventory[blob]['adaptive']['bytes'])
    if best:records.append(best);print(json.dumps(best),flush=True)
    seen.append(blob)
Path('work/pilot_delta_oct27.json').write_text(json.dumps(records,indent=2)+'\n')
