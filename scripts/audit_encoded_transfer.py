"""Audit complete frozen storage-transfer grids without claiming new model replay."""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import statistics
import subprocess

from audit_encoded_storage import files,git_bytes,require,graph_from
from benchmark_planner_efficiency import frozen
from recoverml.core import Graph,canonical,digest
from recoverml.encoded_store import decode,parse_metadata
from recoverml.capability_retention import contract,restricted,retained_bytes
from recoverml.scenario_retention import optimize as reference
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate
from verify_release import Snapshot,evidence_inventory,original_evidence_bytes

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/encoded_storage_transfer_oct26.json'


def block(directory):
    directory=Path(directory);start=json.loads((directory/'run_start.json').read_bytes())
    config=json.loads(CONFIG.read_bytes());group=start['group']
    require(start['config']==config and group in config['groups'],'Frozen transfer protocol differs')
    sources=files(directory/'source_snapshot.tar.gz')
    expected=set(subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',start['commit'],'src/recoverml'],text=True).splitlines())
    expected={p for p in expected if p.endswith('.py')}|{'scripts/benchmark_encoded_transfer.py',
        'scripts/benchmark_planner_efficiency.py','scripts/verify_release.py','configs/encoded_storage_transfer_oct26.json'}
    require(set(sources)==set(start['source_sha256'])==expected,'Transfer source inventory differs')
    for path,sha in start['source_sha256'].items():
        require(digest(sources[path])==sha and sources[path]==git_bytes(start['commit'],path),'Transfer source differs from commit')
    report=json.loads((directory/'report.json').read_bytes());require(not report['source_changed'],'Transfer source changed')
    for name,sha in report['closed_sha256'].items():require(digest((directory/name).read_bytes())==sha,'Closed transfer evidence differs')
    inputs=json.loads((directory/'input_sha256.json').read_bytes())
    for path,sha in inputs.items():
        if path=='results/research/eyeai_complete_oct15/stores_deduplicated.tar.gz':
            snapshot=Snapshot(ROOT,start['commit']);expected_sha=evidence_inventory(snapshot)['expected_sha256'][path]
            raw,_=original_evidence_bytes(snapshot,path,expected_sha)
        else:raw=git_bytes(start['commit'],path)
        require(digest(raw)==sha,'Frozen input bytes differ')
    objects=files(directory/'objects.tar.gz')
    require(all(name==digest(raw)+'.bin' for name,raw in objects.items()),'Transfer object identity differs')
    def obj(sha):return objects[sha+'.bin']
    payloads=json.loads((directory/'payload_inventory.json').read_bytes())
    for blob,record in payloads.items():
        for policy in config['policies']:
            raw=obj(record[policy]['object']);require(len(raw)==record[policy]['bytes'],'Encoded payload length differs')
            require(raw[0] in (range(7) if policy=='adaptive' else (3,6)),'Transfer encoding policy differs')
            decode(raw,record['raw_bytes'],blob)
        require(record['adaptive']['bytes']<=record['gzip9']['bytes'],'Adaptive exceeds an available gzip encoding')
    originals={case:(g,caps,k,size) for case,g,caps,k,size in frozen(group,{})}
    rows=json.loads((directory/'conditions.json').read_bytes())
    require(len(rows)==config['groups'][group] and Counter(r['case'] for r in rows)==Counter({c:1 for c in originals}),
            'Missing, duplicate or replaced frozen condition')
    for row in rows:
        graph,caps,k,expected=originals[row['case']]
        require(obj(row['graph_object'])==canonical(graph.manifest()) and row['capabilities']==caps and row['k']==k and row['raw_exact_bytes']==expected,
                'Original preservation condition differs')
        raw_selected=set(row['raw_selected'])
        require(graph.roots<=raw_selected<=graph.candidates and retained_bytes(graph,raw_selected,caps,k)==expected and
                all(certificate(restricted(graph,caps,f),raw_selected)['complete'] for f in fault_sets(caps,k)),'Frozen raw selection differs')
        missing=sorted(graph.candidates-payloads.keys());missing_selected=sorted(raw_selected-payloads.keys())
        require(row['missing_candidates']==missing and row['missing_selected']==missing_selected,'Unavailable candidates were hidden or replaced')
        status='COMPLETE' if not missing else ('SELECTED_ONLY' if not missing_selected else 'UNAVAILABLE')
        require(row['status']==status,'Transfer availability classification differs')
        methods=set() if missing_selected else {'adaptive_raw_choice','gzip_raw_choice'}
        if not missing:methods|={'adaptive_exact','gzip_exact','adaptive_local','adaptive_snapshots'}
        require(set(row['methods'])==methods,'Available transfer controls differ')
        for method,item in row['methods'].items():
            policy='gzip9' if method.startswith('gzip') else 'adaptive';selected=set(item['selected'])
            require(graph.roots<=selected<=graph.candidates and not selected-payloads.keys(),'Invalid measured retained set')
            header=obj(item['metadata_object'])
            require(parse_metadata(header)==dict(schema=1,format='lossless-per-file-v1',graph=graph.manifest(),contract=json.loads(contract(caps,k))),
                    'Encoded metadata changes original obligations')
            inventory={'metadata.rml':dict(bytes=len(header),sha256=digest(header))}
            inventory.update({'blobs/'+b+'.pkl':dict(bytes=payloads[b][policy]['bytes'],sha256=payloads[b][policy]['object']) for b in selected})
            require(item['inventory']==inventory and item['bytes']==sum(v['bytes'] for v in inventory.values()),'Actual transfer store bytes differ')
            certs=[dict(disabled=list(lost),certificate=certificate(restricted(graph,caps,lost),selected)) for lost in fault_sets(caps,k)]
            require(item['certificates']==certs and all(c['certificate']['complete'] for c in certs),'Conditional recoverability differs')
            if method.endswith('raw_choice'):require(selected==raw_selected,'Raw-choice control changed selection')
            elif method.endswith('snapshots'):
                targets={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
                require(selected==graph.roots|targets,'Snapshot control changes protected targets')
            if method in ('adaptive_exact','gzip_exact'):
                view=Graph(env=graph.env);view.targets=graph.targets;view.roots=graph.roots
                view.nodes={nid:replace(n,size=payloads[n.blob][policy]['bytes']) for nid,n in graph.nodes.items()}
                other,state,diag=reference(view,caps,k,time_limit_s=config['solver_time_limit_s'])
                saved=set(item['reference_selected'])
                require(state=='ok' and diag['storage_optimal'] and
                        sum(view.sizes()[b] for b in other)==sum(view.sizes()[b] for b in selected)==sum(view.sizes()[b] for b in saved),
                        'Independent encoded optimum differs')
                require(all(certificate(restricted(graph,caps,f),saved)['complete'] for f in fault_sets(caps,k)),
                        'Saved oracle optimum is infeasible')
    for status,key in [('COMPLETE','complete'),('SELECTED_ONLY','selected_only'),('UNAVAILABLE','unavailable')]:
        require(report[key]==sum(r['status']==status for r in rows),'Availability total differs')
    require(report['status']=='PASS' and report['conditions']==len(rows) and report['original_payloads_roundtripped']==len(payloads),'Transfer report differs')
    complete_rows=[r for r in rows if r['status']=='COMPLETE']
    raw_wins=sum('adaptive_raw_choice' in r['methods'] and
        1-r['methods'].get('adaptive_exact',r['methods']['adaptive_raw_choice'])['bytes']/r['raw_exact_bytes']>=.1 for r in rows if r['methods'])
    summary=dict(status='PASS',group=group,source_commit=start['commit'],conditions=len(rows),
        complete=report['complete'],selected_only=report['selected_only'],unavailable=report['unavailable'],
        original_payloads_roundtripped=len(payloads),substantial_raw_savings_full_denominator=raw_wins,
        fraction_full_denominator=raw_wins/len(rows),
        median_raw_saving_complete=statistics.median(1-r['methods']['adaptive_exact']['bytes']/r['raw_exact_bytes'] for r in complete_rows) if complete_rows else None,
        median_gzip_saving_complete=statistics.median(1-r['methods']['adaptive_exact']['bytes']/r['methods']['gzip_exact']['bytes'] for r in complete_rows) if complete_rows else None,
        conditions_detail=rows,qualification=config['qualification'],auditor_sha256=digest(Path(__file__).read_bytes()))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=block(args.directory)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='conditions_detail'},indent=2))
