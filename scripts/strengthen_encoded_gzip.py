"""Post-hoc stronger storage control: permit raw fallback for the gzip policy.

Uses original saved gzip bytes and original canonical payloads, never recompresses
them. This strengthens a baseline without changing any execution measurement.
It is an exact byte/closure control, not an additional model replay experiment.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import statistics
import tempfile

from audit_encoded_storage import files,graph_from,require
from recoverml.core import Graph,digest
from recoverml.encoded_store import EncodedStore,decode
from recoverml.component_retention import optimize
from recoverml.scenario_retention import optimize as reference
from recoverml.capability_retention import restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate
from recoverml.broad_workflows import capabilities


def object_id(record,policy):
    value=record[policy]
    return value if isinstance(value,str) else value['object']


def stronger(case,graph,caps,k,payloads,objects,header,adaptive_bytes,recorded=None):
    costs={};fallback=set()
    for blob in graph.candidates:
        item=payloads[blob];gz=objects[object_id(item,'gzip9')+'.bin']
        raw_size=item['raw_bytes'];costs[blob]=min(raw_size+1,len(gz))
        if raw_size+1<len(gz):fallback.add(blob)
    view=Graph(env=graph.env);view.targets=graph.targets;view.roots=graph.roots
    view.nodes={nid:replace(node,size=costs[node.blob]) for nid,node in graph.nodes.items()}
    chosen,status,diag=optimize(view,caps,k,time_limit_s=120.)
    other,ref_status,ref_diag=reference(view,caps,k,time_limit_s=120.)
    require(status=='ok' and ref_status=='ok' and diag['storage_optimal'] and ref_diag['storage_optimal'] and
            sum(costs[b] for b in chosen)==sum(costs[b] for b in other),'Strengthened gzip exact objectives disagree')
    if recorded is not None:
        chosen=set(recorded['selected'])
        require(graph.roots<=chosen<=graph.candidates and sum(costs[b] for b in chosen)==sum(costs[b] for b in other),
                'Published strengthened selection is not optimal')
    require(all(certificate(restricted(graph,caps,f),chosen)['complete'] for f in fault_sets(caps,k)),
            'Strengthened gzip selection is not robust')
    with tempfile.TemporaryDirectory(prefix='recoverml-gzip-fallback-') as temporary:
        store=Path(temporary);(store/'blobs').mkdir();(store/'metadata.rml').write_bytes(header)
        for blob in chosen:
            item=payloads[blob]
            if blob in fallback:
                raw=decode(objects[object_id(item,'adaptive')+'.bin'],item['raw_bytes'],blob)
                encoded=b'\0'+raw
            else:encoded=objects[object_id(item,'gzip9')+'.bin']
            (store/'blobs'/(blob+'.pkl')).write_bytes(encoded)
        reader=EncodedStore(store)
        for blob in chosen:reader.load(blob)
        inventory={p.relative_to(store).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes()))
                   for p in store.rglob('*') if p.is_file()}
    size=sum(v['bytes'] for v in inventory.values())
    result=dict(case=case,strong_gzip_bytes=size,adaptive_bytes=adaptive_bytes,
        saving=1-adaptive_bytes/size,selected=sorted(chosen),inventory=inventory,
        raw_fallback_candidates=len(fallback),raw_fallback_selected=len(fallback&chosen),
        retained_files_roundtripped=len(chosen))
    if recorded is not None:require(result==recorded,'Recreated strengthened control differs')
    return result


def primary(directory,published=None):
    directory=Path(directory);objects=files(directory/'objects.tar.gz')
    captures=json.loads((directory/'captures.json').read_bytes())
    plans=json.loads((directory/'plans.json').read_bytes())
    original=json.loads((directory/'comparisons.json').read_bytes())
    selected={(p['case'],p['method']):p for p in plans}
    graphs={c['history']:(graph_from(objects[c['manifest']+'.bin']),c['payloads']) for c in captures}
    saved={} if published is None else {r['case']:r for r in published['comparisons']}
    rows=[]
    for comparison in original:
        case=comparison['case'];history,loss=case.rsplit('/',1);graph,payloads=graphs[history]
        caps,k,_=capabilities(graph,loss)
        header=objects[selected[case,'gzip_exact']['metadata_object']+'.bin']
        rows.append(stronger(case,graph,caps,k,payloads,objects,header,comparison['sizes']['adaptive_exact'],saved.get(case)))
    result=dict(kind='primary',source_commit=json.loads((directory/'run_start.json').read_bytes())['commit'],
        conditions=len(rows),adaptive_wins=sum(r['saving']>0 for r in rows),ties=sum(r['saving']==0 for r in rows),
        minimum_saving=min(r['saving'] for r in rows),median_saving=statistics.median(r['saving'] for r in rows),
        maximum_saving=max(r['saving'] for r in rows),comparisons=rows,
        qualification='Post-hoc exact storage strengthening. Original saved gzip bytes plus raw fallback; no execution timings or model-replay counts changed.')
    if published is not None:require(result==published,'Published strengthened primary summary differs')
    return result


def transfer(directory,published=None):
    directory=Path(directory);objects=files(directory/'objects.tar.gz')
    payloads=json.loads((directory/'payload_inventory.json').read_bytes())
    cases=json.loads((directory/'conditions.json').read_bytes())
    saved={} if published is None else {r['case']:r for r in published['comparisons']}
    rows=[]
    for row in cases:
        if row['status']!='COMPLETE':continue
        graph=graph_from(objects[row['graph_object']+'.bin'])
        header=objects[row['methods']['gzip_exact']['metadata_object']+'.bin']
        rows.append(stronger(row['case'],graph,row['capabilities'],row['k'],payloads,objects,header,
            row['methods']['adaptive_exact']['bytes'],saved.get(row['case'])))
    result=dict(kind='transfer',group=json.loads((directory/'run_start.json').read_bytes())['group'],
        source_commit=json.loads((directory/'run_start.json').read_bytes())['commit'],conditions=len(cases),complete=len(rows),
        unavailable_objectives=len(cases)-len(rows),adaptive_wins=sum(r['saving']>0 for r in rows),ties=sum(r['saving']==0 for r in rows),
        median_saving=statistics.median(r['saving'] for r in rows) if rows else None,comparisons=rows,
        qualification='Post-hoc byte-level strengthening on complete frozen inputs only; unavailable objectives remain explicit. No new model replay.')
    if published is not None:require(result==published,'Published strengthened transfer summary differs')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--transfer',action='store_true')
    args=parser.parse_args();result=(transfer if args.transfer else primary)(args.directory)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='comparisons'},indent=2))
