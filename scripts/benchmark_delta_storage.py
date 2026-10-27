"""Complete fixed-catalogue byte transfer for lossless prefix/suffix deltas."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import traceback

from threadpoolctl import threadpool_limits
from audit_encoded_storage import files,graph_from,require,git_bytes
from recoverml.core import Graph,canonical,digest
from recoverml.encoded_store import decode,encode,metadata as flat_metadata,parse_metadata
from recoverml.delta_store import DeltaRepresentation,DeltaStore,metadata as delta_metadata
from recoverml.component_retention import optimize
from recoverml.scenario_retention import optimize as reference
from recoverml.robust_heuristics import select,fault_sets
from recoverml.capability_retention import restricted,retained_bytes
from recoverml.witness import certificate

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/delta_storage_oct27.json'
RELEASE='results/research/encoded_storage_oct26/artifact_manifest.json'


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def inputs(originals,key):
    """Authenticate every input member against the previously published release."""
    config=json.loads(CONFIG.read_bytes())
    manifest=json.loads(git_bytes(config['source_release_commit'],RELEASE))
    matches=[r for r in manifest['artifacts'] if ('primary/'+r['dataset']+'/'+r['recipe'] if r['kind']=='primary' else 'transfer/'+r['group'])==key]
    require(len(matches)==1,'Unknown or duplicate input block');record=matches[0]
    directory=Path(originals)/key;prefix='encoded_census' if record['kind']=='primary' else 'encoded_transfer'
    expected={}
    for name,item in record['files'].items():
        relative=name[len(prefix)+1:] if name.startswith(prefix+'/') else 'runner_audit.json'
        raw=(directory/relative).read_bytes()
        require(digest(raw)==item['sha256'] and len(raw)==item['bytes'],'Original input differs: '+relative)
        expected[relative]=item
    objects=files(directory/'objects.tar.gz')
    require(all(name==digest(raw)+'.bin' for name,raw in objects.items()),'Original object identity differs')
    def obj(sha):return objects[sha+'.bin']
    cases=[];raw={};full={}
    if record['kind']=='primary':
        captures=json.loads((directory/'captures.json').read_bytes())
        for capture in captures:
            for blob,item in capture['payloads'].items():
                full[blob]=obj(item['adaptive']);raw[blob]=decode(full[blob],item['raw_bytes'],blob)
        for plan in json.loads((directory/'plans.json').read_bytes()):
            if plan['method']!='adaptive_exact':continue
            m=parse_metadata(obj(plan['metadata_object']));graph=graph_from(canonical(m['graph']))
            cases.append(dict(case=plan['case'],graph=graph,caps=m['contract']['capabilities'],k=m['contract']['maximum_lost_groups'],
                              flat_selected=plan['selected'],flat_bytes=plan['actual_bytes'],availability='COMPLETE'))
        require(len(cases)==9,'Primary denominator differs')
    else:
        for blob,item in json.loads((directory/'payload_inventory.json').read_bytes()).items():
            full[blob]=obj(item['adaptive']['object']);raw[blob]=decode(full[blob],item['raw_bytes'],blob)
        for row in json.loads((directory/'conditions.json').read_bytes()):
            item=row['methods'].get('adaptive_exact')
            cases.append(dict(case=row['case'],graph=graph_from(obj(row['graph_object'])),caps=row['capabilities'],k=row['k'],
                flat_selected=None if item is None else item['selected'],flat_bytes=None if item is None else item['bytes'],availability=row['status']))
        require(len(cases)==config['transfer_conditions'][record['group']],'Frozen denominator differs')
    require(len({r['case'] for r in cases})==len(cases),'Duplicate original condition')
    return cases,raw,full,expected


def solid_control(selected,raw,metadata,cache):
    """Standalone, length-indexed, hash-checked adaptive solid archive control."""
    def container(entries):
        index=canonical([[name,len(data),digest(data)] for name,data in entries])
        payload=len(index).to_bytes(8,'big')+index+b''.join(data for _,data in entries)
        encoded=encode(payload)
        # Decode all bytes before recording the physical control length.
        require(decode(encoded,len(payload),digest(payload))==payload,'Solid archive roundtrip differs')
        return b'RMLSOLID1\n'+len(payload).to_bytes(8,'big')+bytes.fromhex(digest(payload))+encoded
    selected=tuple(sorted(selected));entries=[(b+'.pkl',raw[b]) for b in selected]
    if selected not in cache:cache[selected]=container(entries)
    outside=cache[selected];inside=container([('metadata.rml',metadata)]+entries)
    choice={'archive.rml':inside} if len(inside)<=len(outside)+len(metadata) else {'archive.rml':outside,'metadata.rml':metadata}
    with tempfile.TemporaryDirectory(prefix='recoverml-solid-') as temporary:
        for name,data in choice.items():(Path(temporary)/name).write_bytes(data)
        inventory={p.name:dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in Path(temporary).iterdir()}
    return dict(bytes=sum(i['bytes'] for i in inventory.values()),inventory=inventory,selected=list(selected),metadata_inside='metadata.rml' not in choice)


def run(originals,key,output):
    config=json.loads(CONFIG.read_bytes());output=Path(output);output.mkdir(parents=True,exist_ok=False)
    paths=sorted((ROOT/'src/recoverml').glob('*.py'))+[Path(__file__).resolve(),ROOT/'scripts/audit_delta_storage.py',
        ROOT/'scripts/audit_encoded_storage.py',CONFIG]
    hashes={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in paths}
    start=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),block=key,config=config,
               source_sha256=hashes,timestamp_ns=time.time_ns())
    dump(output/'run_start.json',start)
    with tarfile.open(output/'source_snapshot.tar.gz','w:gz') as archive:
        for p in paths:archive.add(p,arcname=p.relative_to(ROOT))
    cases,raw,full,identities=inputs(originals,key);dump(output/'input_members.json',identities)
    objects=output/'objects';objects.mkdir();representations={};solid_cache={};rows=[];inventories={}
    def put(data):
        sha=digest(data);path=objects/(sha+'.bin')
        if not path.exists():path.write_bytes(data)
        elif path.read_bytes()!=data:raise ValueError('New object collision')
        return sha
    def measured(rep,selected,caps,k):
        with tempfile.TemporaryDirectory(prefix='recoverml-delta-') as temporary:
            path=Path(temporary)/'store';count=rep.write(selected,caps,k,path)
            loaded=DeltaStore(path)
            verified={b:digest(loaded.load(b)) for b in sorted(loaded.retained)}
            require(all(b==sha for b,sha in verified.items()),'Selected delta payload differs')
            certs=[dict(disabled=list(f),certificate=certificate(restricted(rep.graph,caps,f),loaded.retained)) for f in fault_sets(caps,k)]
            require(all(c['certificate']['complete'] for c in certs),'Delta choice violates original loss contract')
            inventory={p.relative_to(path).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in path.rglob('*') if p.is_file()}
            require(count==sum(i['bytes'] for i in inventory.values())==rep.size(selected,caps,k),'Delta store accounting differs')
            return dict(bytes=count,physical_selected=sorted(selected),canonical_selected=sorted(loaded.retained),
                        inventory=inventory,decoded_sha256=verified,certificates=certs)
    with threadpool_limits(limits=1):
        for case in cases:
            g,caps,k=case['graph'],case['caps'],case['k'];row={a:b for a,b in case.items() if a!='graph'}
            graph_sha=digest(canonical(g.manifest()));row['graph_sha256']=graph_sha;row['methods']={}
            if case['availability']!='COMPLETE':
                row['status']=case['availability'];row['missing_candidates']=sorted(g.candidates-raw.keys())
            else:
                if graph_sha not in representations:
                    rep=DeltaRepresentation(g,{b:raw[b] for b in g.candidates},{b:full[b] for b in g.candidates})
                    representations[graph_sha]=rep
                    inventories[graph_sha]=dict(deltas={b:put(data) for b,data in rep.deltas.items()},bases=rep.bases,
                        full={b:digest(full[b]) for b in sorted(g.candidates)},prohibitive=rep.prohibitive)
                    dump(output/'encoding_inventory.json',inventories)
                rep=representations[graph_sha];flat_selected=set(case['flat_selected'])
                old_header=flat_metadata(g,caps,k,'adaptive')
                require(case['flat_bytes']==len(old_header)+sum(len(full[b]) for b in flat_selected),'Saved flat byte objective differs')
                row['methods']['flat_exact']=dict(bytes=case['flat_bytes'],selected=sorted(flat_selected))
                row['methods']['solid_archive_control']=solid_control(flat_selected,raw,old_header,solid_cache)
                selected,status,diag=optimize(rep.cost_graph,caps,k,time_limit_s=config['solver_time_limit_s'])
                other,other_status,other_diag=reference(rep.cost_graph,caps,k,time_limit_s=config['solver_time_limit_s'])
                row['optimizer']=dict(status=status,diagnostic=diag,reference_status=other_status,reference_diagnostic=other_diag)
                certified=(status=='ok' and other_status=='ok' and diag.get('storage_optimal') and other_diag.get('storage_optimal'))
                if not certified:row['status']='UNCERTIFIED'
                else:
                    require(rep.size(selected,caps,k)==rep.size(other,caps,k),'Independent delta objectives disagree')
                    local,local_diag=select(rep.cost_graph,caps,k,retained_bytes(rep.cost_graph,set(rep.full_tokens.values()),caps,k),True)
                    require(local_diag['robust_certified'],'Delta local search failed')
                    normalized=rep.normalize(local);local_diag['normalization_removed']=sorted(local-normalized);local=normalized
                    targets={g.nodes[t].blob for ts in g.targets.values() for t in ts}
                    for method,chosen in [('delta_exact',selected),('delta_local',local),('delta_snapshots',rep.choices(g.roots|targets)),
                                          ('delta_flat_choice',rep.choices(flat_selected))]:
                        row['methods'][method]=measured(rep,chosen,caps,k)
                    row['reference_selected']=sorted(other);row['local_diagnostic']=local_diag
                    row['production_bytes']=min(case['flat_bytes'],row['methods']['delta_exact']['bytes'])
                    row['production_format']='delta' if row['production_bytes']<case['flat_bytes'] else 'flat'
                    row['status']='COMPLETE'
            rows.append(row);dump(output/'conditions.json',rows)
            print(key,case['case'],row['status'],{m:x['bytes'] for m,x in row['methods'].items()},flush=True)
    with tarfile.open(output/'objects.tar.gz','w:gz') as archive:
        for p in sorted(objects.iterdir()):archive.add(p,arcname=p.name)
    changed=[p for p,sha in hashes.items() if digest((ROOT/p).read_bytes())!=sha]
    dump(output/'report.json',dict(status='PASS' if not changed else 'FAIL',conditions=len(rows),source_changed=changed,
        complete=sum(r['status']=='COMPLETE' for r in rows),uncertified=sum(r['status']=='UNCERTIFIED' for r in rows),
        original_payloads_verified=len(raw),closed_sha256={p.name:digest(p.read_bytes()) for p in output.iterdir() if p.is_file()},
        qualification=config['qualification']))
    require(not changed,'Source changed during experiment')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--originals',type=Path,required=True)
    parser.add_argument('--block',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:run(args.originals,args.block,args.output)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True);(args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
