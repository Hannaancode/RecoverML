"""Verify delta inventory, original bytes, complete grid and independent optima."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from audit_encoded_storage import files,require,git_bytes
from benchmark_delta_storage import inputs,solid_control,CONFIG,ROOT
from recoverml.core import canonical,digest
from recoverml.encoded_store import decode,metadata as flat_metadata
from recoverml.delta_store import DeltaRepresentation,delta,overlap,descriptor,metadata as delta_metadata,HEADER
from recoverml.capability_retention import restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.scenario_retention import optimize as reference
from recoverml.witness import certificate


def audit(originals,directory,preflight=False):
    directory=Path(directory);start=json.loads((directory/'run_start.json').read_bytes());config=json.loads(CONFIG.read_bytes())
    require(start['config']==config,'Delta protocol differs')
    source=files(directory/'source_snapshot.tar.gz')
    required={'scripts/benchmark_delta_storage.py','scripts/audit_delta_storage.py','scripts/audit_encoded_storage.py','configs/delta_storage_oct27.json'}
    if preflight:required|={p.relative_to(ROOT).as_posix() for p in (ROOT/'src/recoverml').glob('*.py')}
    else:
        required|={p for p in subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',start['commit'],'src/recoverml'],text=True).splitlines() if p.endswith('.py')}
    require(set(source)==set(start['source_sha256'])==required,'Delta source inventory differs')
    for path,sha in start['source_sha256'].items():
        require(digest(source[path])==sha,'Archived source hash differs')
        if not preflight:require(source[path]==git_bytes(start['commit'],path),'Source does not match pinned commit')
    report=json.loads((directory/'report.json').read_bytes());require(report['status']=='PASS' and not report['source_changed'],'Incomplete delta run')
    for path,sha in report['closed_sha256'].items():require(digest((directory/path).read_bytes())==sha,'Closed evidence differs')
    cases,raw,full,identities=inputs(originals,start['block'])
    require(json.loads((directory/'input_members.json').read_bytes())==identities,'Input member identities differ')
    rows=json.loads((directory/'conditions.json').read_bytes());originals_by_case={r['case']:r for r in cases}
    require(Counter(r['case'] for r in rows)==Counter({c:1 for c in originals_by_case}),'Missing/duplicate/replaced delta condition')
    objects=files(directory/'objects.tar.gz');require(all(name==digest(data)+'.bin' for name,data in objects.items()),'Delta object differs')
    inventory=json.loads((directory/'encoding_inventory.json').read_bytes()) if (directory/'encoding_inventory.json').exists() else {}
    reconstructed={};solid_cache={};used=set();checks=0
    for row in rows:
        old=originals_by_case[row['case']];g,caps,k=old['graph'],old['caps'],old['k']
        for field in ('caps','k','flat_selected','flat_bytes','availability'):require(row[field]==old[field],'Original condition changed')
        graph_sha=digest(canonical(g.manifest()));require(graph_sha==row['graph_sha256'],'Original graph differs')
        if old['availability']!='COMPLETE':
            require(row['status']==old['availability'] and not row['methods'] and row['missing_candidates']==sorted(g.candidates-raw.keys()),'Unavailable condition concealed')
            continue
        used.add(graph_sha)
        if graph_sha not in reconstructed:
            item=inventory[graph_sha];rep=DeltaRepresentation.__new__(DeltaRepresentation)
            rep.graph=g;rep.full={b:full[b] for b in g.candidates};rep.deltas={};rep.bases={};previous=[]
            for blob in sorted(g.candidates,key=lambda b:(g.sizes()[b],b)):
                choices=[]
                if blob not in g.roots:
                    for base in previous:
                        prefix,suffix=overlap(raw[base],raw[blob])
                        if prefix+suffix>=config['minimum_overlap_bytes']:choices.append((-(prefix+suffix),base))
                    if choices:
                        base=min(choices)[1];candidate=delta(base,raw[base],raw[blob])
                        if len(candidate)<len(full[blob]):
                            sha=item['deltas'][blob];encoded=objects[sha+'.bin']
                            require(encoded==candidate,'Declared delta candidate differs')
                            base,prefix,suffix,middle_size,middle_sha=descriptor(encoded,g.sizes()[blob])
                            middle=decode(encoded[HEADER:],middle_size,middle_sha)
                            actual=raw[base][:prefix]+middle+(raw[base][-suffix:] if suffix else b'')
                            require(actual==raw[blob] and digest(actual)==blob,'Independent delta reconstruction differs')
                            rep.deltas[blob]=encoded;rep.bases[blob]=base
                previous.append(blob)
            require(set(rep.deltas)==set(item['deltas']) and rep.bases==item['bases'] and item['full']=={b:digest(full[b]) for b in sorted(g.candidates)},'Encoding inventory differs')
            rep._cost_graph();require(rep.prohibitive==item['prohibitive'],'Virtual cost bound differs');reconstructed[graph_sha]=rep
        rep=reconstructed[graph_sha];flat=set(old['flat_selected']);header=flat_metadata(g,caps,k,'adaptive')
        require(row['methods']['flat_exact']==dict(bytes=len(header)+sum(len(full[b]) for b in flat),selected=sorted(flat)),'Flat optimum comparison differs')
        require(row['methods']['solid_archive_control']==solid_control(flat,raw,header,solid_cache),'Solid archive control differs')
        if row['status']=='UNCERTIFIED':
            require(set(row['methods'])=={'flat_exact','solid_archive_control'},'Uncertified optimum misrepresented');continue
        require(row['status']=='COMPLETE' and set(row['methods'])==set(config['methods']),'Delta methods differ')
        other,status,diag=reference(rep.cost_graph,caps,k,time_limit_s=config['solver_time_limit_s'])
        require(status=='ok' and diag['storage_optimal'] and diag['robust_certified'],'Independent recheck not certified')
        optimum=rep.size(other,caps,k)
        for method in ('delta_exact','delta_local','delta_snapshots','delta_flat_choice'):
            result=row['methods'][method];selected=set(result['physical_selected']);mapping=rep.files(selected)
            if method=='delta_local':
                initial=selected|set(row['local_diagnostic']['normalization_removed'])
                require(rep.normalize(initial)==selected,'Local representation normalization differs')
            canonical_set=set(mapping);new_header=delta_metadata(g,caps,k)
            expected={'metadata.rml':dict(bytes=len(new_header),sha256=digest(new_header))}
            expected.update({'blobs/'+b+'.pkl':dict(bytes=len(data),sha256=digest(data)) for b,data in mapping.items()})
            require(result['inventory']==expected and result['bytes']==sum(i['bytes'] for i in expected.values()),'Complete delta store byte count differs')
            require(result['canonical_selected']==sorted(canonical_set) and result['decoded_sha256']=={b:b for b in canonical_set},'Selected decoding receipt differs')
            # Independently rebuild every selected file from its retained bases.
            decoded={}
            for blob in sorted(canonical_set,key=lambda b:(g.sizes()[b],b)):
                encoded=mapping[blob]
                if encoded[0]!=7:value=decode(encoded,g.sizes()[blob],blob)
                else:
                    base,prefix,suffix,n,sha=descriptor(encoded,g.sizes()[blob])
                    require(base in decoded,'Base must be physically retained and earlier')
                    value=decoded[base][:prefix]+decode(encoded[HEADER:],n,sha)+(decoded[base][-suffix:] if suffix else b'')
                require(value==raw[blob] and digest(value)==blob,'Selected file reconstruction differs');decoded[blob]=value;checks+=1
            certs=[dict(disabled=list(f),certificate=certificate(restricted(g,caps,f),canonical_set)) for f in fault_sets(caps,k)]
            require(result['certificates']==certs and all(c['certificate']['complete'] for c in certs),'Original fault-set guarantees differ')
            require(result['bytes']>=optimum,'Method below certified same-format optimum')
            if method=='delta_exact':require(result['bytes']==optimum,'Recorded delta optimum differs')
            if method in ('delta_snapshots','delta_flat_choice'):
                original=flat if method=='delta_flat_choice' else g.roots|{g.nodes[t].blob for ts in g.targets.values() for t in ts}
                require(selected==rep.choices(original),'Fixed-selection control changed')
        reference_saved=set(row['reference_selected'])
        require(rep.size(reference_saved,caps,k)==optimum and all(certificate(restricted(rep.cost_graph,caps,f),reference_saved)['complete'] for f in fault_sets(caps,k)), 'Saved oracle selection differs')
        require(row['production_bytes']==min(old['flat_bytes'],optimum) and row['production_format']==('delta' if optimum<old['flat_bytes'] else 'flat'),'Production fallback differs')
    require(used==set(inventory),'Unexpected or missing graph inventory')
    require(set(objects)=={sha+'.bin' for item in inventory.values() for sha in item['deltas'].values()},'Unreferenced or missing delta objects')
    require(report['conditions']==len(rows) and report['complete']==sum(r['status']=='COMPLETE' for r in rows) and
            report['uncertified']==sum(r['status']=='UNCERTIFIED' for r in rows) and report['original_payloads_verified']==len(raw),'Report totals differ')
    return dict(status='PASS',preflight=preflight,block=start['block'],source_commit=start['commit'],conditions=len(rows),
        complete=report['complete'],uncertified=report['uncertified'],selected_payloads_verified=checks,
        conditions_sha256=digest((directory/'conditions.json').read_bytes()),encoding_inventory_sha256=digest(canonical(inventory)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--originals',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args();result=audit(args.originals,args.directory,args.preflight)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
