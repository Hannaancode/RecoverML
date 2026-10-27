"""Full-denominator engineering follow-up: executable solid stores and equal-format local controls."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

from benchmark_delta_storage import inputs
from audit_encoded_storage import require,git_bytes
from recoverml.core import canonical,digest
from recoverml.solid_store import SolidRepresentation,SolidStore
from recoverml.capability_retention import restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate

ROOT=Path(__file__).resolve().parents[1]
BASELINE='6965f41cec4444eb41e135d1f04297bab24de340'


def run(originals,final,key):
    source_paths=sorted((ROOT/'src/recoverml').glob('*.py'))+[Path(__file__).resolve(),ROOT/'scripts/benchmark_delta_storage.py',ROOT/'scripts/audit_encoded_storage.py']
    provenance=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in source_paths},
        working_tree_dirty=bool(subprocess.check_output(['git','status','--porcelain','--','src','scripts'],cwd=ROOT,text=True).strip()))
    cases,raw,full,identities=inputs(originals,key);path=Path(final)/key
    manifest=json.loads(git_bytes(BASELINE,'results/research/delta_storage_oct27/artifact_manifest.json'))
    records=[r for r in manifest['final']['artifacts'] if r['block']==key]
    require(len(records)==1,'Unknown delta source block')
    for name,expected in records[0]['files'].items():
        relative=name[len('delta/'):] if name.startswith('delta/') else 'runner_audit.json'
        data=(path/relative).read_bytes()
        require(len(data)==expected['bytes'] and digest(data)==expected['sha256'],'Delta source member differs: '+relative)
    prior={r['case']:r for r in json.loads((path/'conditions.json').read_bytes())}
    require(set(prior)=={case['case'] for case in cases},'Solid denominator differs from the previous grid')
    proof=git_bytes(BASELINE,'results/research/delta_storage_oct27/strengthened_local.json.gz')
    strong={r['case']:r for r in json.loads(gzip.decompress(proof))[key]['rows']}
    reps={};rows=[]
    for case in cases:
        old=prior[case['case']];row=dict(case=case['case'],status=old['status'])
        if row['status']!='COMPLETE':rows.append(row);continue
        graph=case['graph'];caps=case['caps'];k=case['k'];graph_sha=digest(canonical(graph.manifest()))
        if graph_sha not in reps:reps[graph_sha]=SolidRepresentation(graph,{b:raw[b] for b in graph.candidates})
        rep=reps[graph_sha];methods={};checked={}
        selections={'solid_flat_exact':case['flat_selected'],
                    'solid_previous_local':strong[case['case']]['old_selected'],
                    'solid_fresh_delta_local':old['methods']['delta_local']['canonical_selected']}
        for method,selection in selections.items():
            selected=tuple(sorted(selection))
            if selected not in checked:
                with tempfile.TemporaryDirectory(prefix='recoverml-solid-grid-') as temporary:
                    store=Path(temporary)/'store';size=rep.write(selected,caps,k,store);loaded=SolidStore(store)
                    require(loaded.retained==set(selected),'Solid retained set differs')
                    verified={b:digest(loaded.load(b)) for b in sorted(loaded.retained)}
                    require(verified=={b:b for b in selected},'Solid decoded payload differs')
                    inventory={p.name:dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in store.iterdir()}
                    require(size==sum(v['bytes'] for v in inventory.values()),'Solid actual byte accounting differs')
                    certificates=[dict(disabled=f,complete=certificate(restricted(graph,caps,f),set(selected))['complete']) for f in fault_sets(caps,k)]
                    require(all(c['complete'] for c in certificates),'Solid loss contract failed')
                    retained_targets=sorted(n for n in loaded.protected if graph.nodes[n].blob in loaded.retained)
                    export=None if not retained_targets else loaded.recover(Path(temporary)/'export',target_ids=retained_targets)
                    checked[selected]=dict(bytes=size,selected=list(selected),inventory=inventory,decoded_sha256=verified,
                        decoded_retained_bytes=sum(len(raw[b]) for b in selected),certificates=certificates,retained_target_export=export)
            methods[method]=checked[selected]
        baseline=old['methods']['solid_archive_control'];actual=methods['solid_flat_exact']
        require(actual['bytes']==baseline['bytes'] and actual['inventory']==baseline['inventory'],'Executable solid store differs from published byte control')
        production_options={'flat':case['flat_bytes'],'delta':old['methods']['delta_exact']['bytes'],'solid-flat':actual['bytes']}
        local_options=dict(strong[case['case']]['options'])
        local_options.update({m:methods[m]['bytes'] for m in ('solid_previous_local','solid_fresh_delta_local')})
        winner=min(production_options,key=lambda name:(production_options[name],name))
        local_winner=min(local_options,key=lambda name:(local_options[name],name))
        row.update(methods=methods,production_options=production_options,production_format=winner,production_bytes=production_options[winner],
            equal_format_local_options=local_options,equal_format_local_choice=local_winner,equal_format_local_bytes=local_options[local_winner],
            previous_production_bytes=old['production_bytes'],previous_flat_bytes=case['flat_bytes'],
            unique_selected_sets_checked=len(checked),selected_file_checks=sum(len(item['selected']) for item in checked.values()))
        rows.append(row);print(key+' '+case['case']+' verified',flush=True)
    return dict(block=key,conditions=len(rows),rows=rows,
        **provenance,baseline_commit=BASELINE,
        original_members=identities,delta_source_members=records[0]['files'],stronger_local_proof_sha256=digest(proof),
        qualification='Post-hoc storage engineering follow-up using every previous condition. Actual durable stores and retained-target exports checked; allowed-loss certificates checked. No new full-grid ML replay, latency, memory benchmark, or global joint-compression optimum.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--originals',type=Path,required=True)
    parser.add_argument('--final',type=Path,required=True);parser.add_argument('--block',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(not args.output.exists(),'Choose a fresh solid result path')
    result=run(args.originals,args.final,args.block);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status='PASS',block=result['block'],conditions=result['conditions'])))
