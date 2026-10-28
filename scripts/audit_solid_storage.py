"""Rebuild independent solid controls and verify the production portfolio's plans."""
import argparse
from dataclasses import replace
import gzip
import io
import json
from pathlib import Path
import subprocess
import tarfile

from audit_encoded_storage import require,files,git_bytes
from benchmark_delta_storage import inputs,solid_control
from benchmark_solid_storage import BASELINE
from recoverml.core import Graph,canonical,digest
from recoverml.encoded_store import Representation,metadata
from recoverml.delta_store import DeltaRepresentation
from recoverml.solid_store import local_selections
from recoverml.capability_retention import restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate

ROOT=Path(__file__).resolve().parents[1]


def source_check(directory,record,source_commit):
    require(record['source_commit']==source_commit and record['baseline_commit']==BASELINE and record['working_tree_dirty'] is False,'Unpinned solid execution')
    paths=['src/recoverml','scripts/benchmark_solid_storage.py','scripts/benchmark_delta_storage.py','scripts/audit_encoded_storage.py',
           'configs/delta_storage_oct27.json','requirements.txt','docs/SOLID_STORAGE_OCT27.md']
    original=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=tar',source_commit,*paths],cwd=ROOT)
    def content(raw):
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as archive:
            members=[m for m in archive.getmembers() if not m.isdir()]
            require(all(m.isfile() for m in members) and len({m.name for m in members})==len(members),'Invalid source snapshot')
            return {m.name:archive.extractfile(m).read() for m in members}
    expected=content(original);captured=content((Path(directory)/'source_snapshot.tar.gz').read_bytes())
    require(captured==expected,'Captured source differs from the Git commit')
    expected_hashes={p:digest(raw) for p,raw in expected.items() if (p.startswith('src/recoverml/') and p.count('/')==2 and p.endswith('.py')) or p in paths[1:4]}
    require(record['source_sha256']==expected_hashes,'Recorded source inventory differs')


def audit(directory,originals,delta,source_commit):
    directory=Path(directory);record=json.loads((directory/'result.json').read_bytes());key=record['block']
    source_check(directory,record,source_commit)
    cases,raw,full,identities=inputs(originals,key)
    require(record['original_members']==identities and record['conditions']==len(cases),'Original identities or denominator differ')
    baseline_manifest=json.loads(git_bytes(BASELINE,'results/research/delta_storage_oct27/artifact_manifest.json'))
    expected_record=next(r for r in baseline_manifest['final']['artifacts'] if r['block']==key)
    require(record['delta_source_members']==expected_record['files'],'Delta source identities differ')
    old_path=Path(delta)/key
    for name,identity in expected_record['files'].items():
        path=old_path/(name[len('delta/'):] if name.startswith('delta/') else 'runner_audit.json');data=path.read_bytes()
        require(len(data)==identity['bytes'] and digest(data)==identity['sha256'],'Delta baseline member differs')
    old_rows={r['case']:r for r in json.loads((old_path/'conditions.json').read_bytes())}
    proof=git_bytes(BASELINE,'results/research/delta_storage_oct27/strengthened_local.json.gz')
    require(record['stronger_local_proof_sha256']==digest(proof),'Stronger local source differs')
    strong={r['case']:r for r in json.loads(gzip.decompress(proof))[key]['rows']}
    inventory=json.loads((old_path/'encoding_inventory.json').read_bytes()) if (old_path/'encoding_inventory.json').exists() else {}
    objects=files(old_path/'objects.tar.gz');representations={};control_cache={};outcomes=[];payload_checks=0;export_checks=0
    require(len(record['rows'])==len(cases) and {r['case'] for r in record['rows']}=={c['case'] for c in cases},'Missing or repeated solid condition')
    saved={r['case']:r for r in record['rows']}
    for case in cases:
        row=saved[case['case']];old=old_rows[case['case']];require(row['status']==old['status'],'Availability differs')
        result=dict(case=case['case'],status=row['status'])
        if row['status']!='COMPLETE':outcomes.append(result);continue
        graph=case['graph'];caps=case['caps'];k=case['k'];graph_sha=digest(canonical(graph.manifest()))
        if graph_sha not in representations:
            flat=Representation.__new__(Representation);flat.graph=graph;flat.policy='adaptive';flat.encoded={b:full[b] for b in graph.candidates}
            flat.cost_graph=Graph(env=graph.env);flat.cost_graph.nodes={nid:replace(node,size=len(full[node.blob])) for nid,node in graph.nodes.items()}
            flat.cost_graph.targets={v:list(ts) for v,ts in graph.targets.items()};flat.cost_graph.roots=set(graph.roots)
            coupled=DeltaRepresentation.__new__(DeltaRepresentation);coupled.graph=graph;coupled.full=flat.encoded
            coupled.deltas={b:objects[sha+'.bin'] for b,sha in inventory[graph_sha]['deltas'].items()};coupled.bases=inventory[graph_sha]['bases'];coupled._cost_graph()
            representations[graph_sha]=(flat,coupled)
        flat,coupled=representations[graph_sha];local=local_selections(flat,coupled,caps,k)
        require(local['solid-flat-local']==set(strong[case['case']]['old_selected']),'Online flat local selection differs')
        require(local['solid-delta-local']==set(old['methods']['delta_local']['canonical_selected']),'Online delta local selection differs')
        selections={'solid_flat_exact':set(case['flat_selected']),'solid_previous_local':local['solid-flat-local'],'solid_fresh_delta_local':local['solid-delta-local']}
        unique={}
        require(set(row['methods'])==set(selections),'Missing or replaced solid method')
        for method,selected in selections.items():
            item=row['methods'][method];require(item['selected']==sorted(selected),'Solid selected set differs')
            signature=tuple(sorted(selected))
            if signature not in unique:
                control=solid_control(selected,raw,metadata(graph,caps,k,'adaptive'),control_cache)
                require(item['bytes']==control['bytes'] and item['inventory']==control['inventory'],'Independent solid byte reconstruction differs')
                require(item['decoded_sha256']=={b:b for b in selected},'Selected hash evidence differs')
                require(item['decoded_retained_bytes']==sum(len(raw[b]) for b in selected),'Decoded retained bytes differ')
                certs=[dict(disabled=list(f),complete=certificate(restricted(graph,caps,f),selected)['complete']) for f in fault_sets(caps,k)]
                require(item['certificates']==certs and all(c['complete'] for c in certs),'Solid loss certificate differs')
                targets={graph.nodes[n].blob for ts in graph.targets.values() for n in ts if graph.nodes[n].blob in selected}
                exported=item['retained_target_export']
                if not targets:require(exported is None,'Unexpected retained target export')
                else:
                    require(exported['status']=='PASS' and exported['mode']=='solid_export' and exported['operations']==[],'Export evidence differs')
                    require(exported['target_sha256']=={b:b for b in targets} and exported['temporary_store_bytes']==0,'Exported identities differ')
                    require(exported['decoded_retained_bytes']==item['decoded_retained_bytes'],'Export decoded size differs')
                payload_checks+=len(selected);export_checks+=len(targets);unique[signature]=item
            else:require(item==unique[signature],'Repeated selection has inconsistent evidence')
        require(row['unique_selected_sets_checked']==len(unique) and row['selected_file_checks']==sum(len(v['selected']) for v in unique.values()),'Selected-file check count differs')
        require(flat.size(case['flat_selected'],caps,k)==case['flat_bytes'],'Flat bytes differ')
        require(coupled.size(old['methods']['delta_exact']['physical_selected'],caps,k)==old['methods']['delta_exact']['bytes'],'Delta bytes differ')
        three={'flat':case['flat_bytes'],'delta':old['methods']['delta_exact']['bytes'],'solid-flat':row['methods']['solid_flat_exact']['bytes']}
        require(row['production_options']==three and row['production_bytes']==min(three.values()),'Original three-candidate result differs')
        local_options=dict(strong[case['case']]['options']);local_options.update({name:row['methods'][name]['bytes'] for name in ('solid_previous_local','solid_fresh_delta_local')})
        require(row['equal_format_local_options']==local_options and row['equal_format_local_bytes']==min(local_options.values()),'Equal-format local control differs')
        five={**three,'solid-flat-local':row['methods']['solid_previous_local']['bytes'],'solid-delta-local':row['methods']['solid_fresh_delta_local']['bytes']}
        winner=min(five,key=lambda name:(five[name],name));require(five[winner]<=row['equal_format_local_bytes'],'Portfolio is larger than its included local control')
        result.update(previous_flat_bytes=case['flat_bytes'],previous_delta_bytes=old['production_bytes'],three_candidate_bytes=row['production_bytes'],
            equal_format_local_bytes=row['equal_format_local_bytes'],solid_control_bytes=three['solid-flat'],candidate_bytes=five,
            production_format=winner,production_bytes=five[winner])
        outcomes.append(result)
    return dict(status='PASS',block=key,conditions=len(outcomes),source_commit=source_commit,selected_file_checks=payload_checks,
        retained_target_export_checks=export_checks,rows=outcomes,
        qualification='Original cloud source and ZIP identities checked; independent archive controls rebuilt, loss certificates rechecked, and both online local selectors reproduced. Five-candidate choice is a disclosed post-hoc correction; no new model replay or timing experiment.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--originals',type=Path,required=True)
    parser.add_argument('--delta',type=Path,required=True);parser.add_argument('--source-commit',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'Choose a fresh audit output');result=audit(args.directory,args.originals,args.delta,args.source_commit)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
