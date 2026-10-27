"""Post-hoc stronger local control: retain previous best plans as valid options.

Adding representation nodes can harm a heuristic's search. Give it the minimum
of its previous flat plan, that plan converted to deltas, and its newly measured
delta-graph plan. This control never claims new ML replay or new timing data.
"""
import argparse
import gzip
import json
from pathlib import Path
import tempfile

from audit_encoded_storage import files,require
from benchmark_delta_storage import inputs
from recoverml.core import canonical,digest
from recoverml.delta_store import DeltaRepresentation,DeltaStore,metadata
from recoverml.encoded_store import metadata as flat_metadata
from recoverml.capability_retention import restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate

ROOT=Path(__file__).resolve().parents[1]


def block(originals,final,key,proof=None):
    cases,raw,full,identities=inputs(originals,key)
    prior=Path(originals)/key;path=Path(final)/key
    if key.startswith('primary/'):
        local={r['case']:dict(bytes=r['actual_bytes'],selected=r['selected']) for r in json.loads((prior/'plans.json').read_bytes()) if r['method']=='adaptive_local'}
    else:
        local={r['case']:r['methods']['adaptive_local'] for r in json.loads((prior/'conditions.json').read_bytes()) if 'adaptive_local' in r['methods']}
    rows={r['case']:r for r in json.loads((path/'conditions.json').read_bytes())}
    inventory=json.loads((path/'encoding_inventory.json').read_bytes()) if (path/'encoding_inventory.json').exists() else {}
    objects=files(path/'objects.tar.gz');reps={};result=[]
    for case in cases:
        record=dict(case=case['case'],status=rows[case['case']]['status'])
        if record['status']!='COMPLETE':result.append(record);continue
        graph=case['graph'];caps=case['caps'];k=case['k'];sha=digest(canonical(graph.manifest()))
        if sha not in reps:
            rep=DeltaRepresentation.__new__(DeltaRepresentation);rep.graph=graph;rep.full={b:full[b] for b in graph.candidates}
            rep.deltas={b:objects[s+'.bin'] for b,s in inventory[sha]['deltas'].items()};rep.bases=inventory[sha]['bases'];rep._cost_graph();reps[sha]=rep
        rep=reps[sha];old=local[case['case']];selected=set(old['selected']);header=flat_metadata(graph,caps,k,'adaptive')
        require(old['bytes']==len(header)+sum(len(full[b]) for b in selected),'Previous local physical bytes differ')
        require(all(certificate(restricted(graph,caps,f),selected)['complete'] for f in fault_sets(caps,k)),'Previous local plan is not feasible')
        converted=rep.choices(selected)
        with tempfile.TemporaryDirectory(prefix='recoverml-strong-delta-local-') as temporary:
            store=Path(temporary)/'store';size=rep.write(converted,caps,k,store);loaded=DeltaStore(store)
            verified={b:digest(loaded.load(b)) for b in sorted(loaded.retained)}
            require(verified=={b:b for b in selected},'Converted local plan changes canonical values')
            saved={p.relative_to(store).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in store.rglob('*') if p.is_file()}
            require(size==sum(v['bytes'] for v in saved.values()),'Converted local accounting differs')
        choices={'previous_flat_local':old['bytes'],'previous_local_converted_to_delta':size,
                 'fresh_delta_graph_local':rows[case['case']]['methods']['delta_local']['bytes']}
        choice=min(choices,key=lambda c:(choices[c],c));ours=rows[case['case']]['production_bytes']
        require(ours<=choices[choice],'Stronger local control is below the certified format minima')
        record.update(production_bytes=ours,strong_local_bytes=choices[choice],choice=choice,options=choices,
            old_selected=sorted(selected),converted_physical_selected=sorted(converted),converted_inventory=saved,
            decoded_sha256=verified,saving=1-ours/choices[choice])
        result.append(record)
    value=dict(block=key,conditions=len(result),rows=result)
    if proof is not None:require(value==proof,'Saved strengthened local proof differs')
    return value


def complete(originals,final,published=None):
    config=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    keys=['primary/'+d+'/'+r for d in config['datasets'] for r in config['recipes']]+['transfer/'+g for g in ('scientific','cloud','retinal','letter')]
    result={}
    for key in keys:
        result[key]=block(originals,final,key,None if published is None else published[key]);print('Strengthened '+key,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--originals',type=Path,required=True)
    parser.add_argument('--final',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify-proof',type=Path);args=parser.parse_args()
    published=None if args.verify_proof is None else json.loads(gzip.decompress(args.verify_proof.read_bytes()))
    value=complete(args.originals,args.final,published);args.output.parent.mkdir(parents=True,exist_ok=True)
    if published is None:
        with args.output.open('xb') as stream:stream.write(gzip.compress(canonical(value),compresslevel=9,mtime=0))
    else:
        rows=[r for b in value.values() for r in b['rows']]
        receipt=dict(status='PASS',blocks=len(value),conditions=len(rows),complete=sum(r['status']=='COMPLETE' for r in rows),
            converted_payloads_verified=sum(len(r.get('decoded_sha256',{})) for r in rows),
            proof_sha256=digest(args.verify_proof.read_bytes()),auditor_sha256=digest(Path(__file__).read_bytes()),
            qualification='Post-hoc stronger byte control; previous plans and their delta conversions verified. No new model replay or timing data.')
        with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
