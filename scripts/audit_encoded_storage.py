"""Reconcile original encoded bytes, exact objectives and every recovery request."""
import argparse
from collections import Counter
from dataclasses import replace
from functools import lru_cache
import gzip
import itertools
import json
from pathlib import Path
import re
import statistics
import subprocess
import tarfile

from recoverml.core import Graph,Node,canonical,digest
from recoverml.encoded_store import decode,parse_metadata
from recoverml.capability_retention import contract,retained_bytes,restricted
from recoverml.broad_workflows import capabilities
from recoverml.robust_heuristics import fault_sets
from recoverml.scenario_retention import optimize as reference
from recoverml.witness import certificate
from recoverml.published_materializers import REVISION,SOURCE_SHA256

ROOT=Path(__file__).resolve().parents[1]


def require(ok,message):
    if not ok:raise ValueError(message)


def files(path):
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        require(all(m.isfile() for m in members),'Only regular evidence members allowed')
        require(len(members)==len({m.name for m in members}),'Duplicate evidence member')
        require(all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and '\\' not in m.name and ':' not in m.name
                    for m in members),'Unsafe evidence member')
        return {m.name:archive.extractfile(m).read() for m in members}


def graph_from(raw):
    record=json.loads(raw);graph=Graph(env=record['environment'])
    graph.nodes={n['id']:Node(**n) for n in record['nodes']}
    graph.targets=record['targets'];graph.roots=set(record['mandatory_blobs'])
    return graph


@lru_cache(maxsize=None)
def git_bytes(commit,path):return subprocess.check_output(['git','-C',str(ROOT),'show',commit+':'+path])


def check_grid(rows,cases,methods,faults):
    expected=Counter({(case,method,tuple(lost)):1 for case in cases for method in methods for lost in faults[case]})
    require(Counter((r['case'],r['method'],tuple(r['disabled'])) for r in rows)==expected,'Missing, duplicate or replaced request')


def block(directory,smoke=False,preflight=False):
    directory=Path(directory)
    start=json.loads((directory/'run_start.json').read_bytes())
    config=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    if smoke:config=dict(config,versions=[1])
    require(start['config']==config and start['smoke']==smoke,'Frozen protocol or smoke classification differs')
    require(not preflight or smoke,'Preflight cannot bypass full-source identity')
    source=files(directory/'source_snapshot.tar.gz')
    expected={p.relative_to(ROOT).as_posix() for p in (ROOT/'src/recoverml').glob('*.py')}|{
        'scripts/benchmark_encoded_storage.py','configs/encoded_storage_oct26.json'}
    if not preflight:
        expected=set(subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',start['commit'],'src/recoverml'],text=True).splitlines())
        expected={p for p in expected if p.endswith('.py')}|{'scripts/benchmark_encoded_storage.py','configs/encoded_storage_oct26.json'}
    require(set(source)==set(start['source_sha256'])==expected,'Incomplete source snapshot')
    for path,sha in start['source_sha256'].items():
        require(digest(source[path])==sha,'Archived source hash differs')
        if not preflight:require(git_bytes(start['commit'],path)==source[path],'Archived source differs from source commit')
    require(start['hyppo_revision']==REVISION and start['hyppo_source_sha256']==SOURCE_SHA256,'Pinned HYPPO identity differs')
    report=json.loads((directory/'report.json').read_bytes())
    require(not report['source_changed'],'Runtime source changed')
    for name,sha in report['closed_sha256'].items():require(digest((directory/name).read_bytes())==sha,'Closed evidence differs')
    objects=files(directory/'objects.tar.gz')
    require(all(re.fullmatch(r'[0-9a-f]{64}\.bin',name) and digest(raw)==name[:-4] for name,raw in objects.items()),'Object identity differs')
    def obj(identity):return objects[identity+'.bin']
    captures=json.loads((directory/'captures.json').read_bytes())
    dataset,recipe=start['dataset'],start['recipe']
    histories={f'{dataset}/{recipe}/v{v}' for v in config['versions']}
    require(len(captures)==len(histories) and {r['history'] for r in captures}==histories,'Capture grid differs')
    graphs={};views={};payloads={};decoded_count=0
    for capture in captures:
        graph=graph_from(obj(capture['manifest']));history=capture['history'];versions=int(history.rsplit('/v',1)[1])
        require(len(graph.targets)==versions and len(graph.nodes)==4+2*versions,'Captured history dimensions differ')
        require(set(capture['payloads'])==graph.candidates,'Capture payload inventory differs')
        graphs[history]=graph;payloads[history]=capture['payloads'];views[history]={}
        for policy in ('adaptive','gzip9'):
            view=Graph(env=graph.env)
            view.nodes={nid:replace(n,size=len(obj(capture['payloads'][n.blob][policy]))) for nid,n in graph.nodes.items()}
            view.targets=graph.targets;view.roots=graph.roots;views[history][policy]=view
            for blob,item in capture['payloads'].items():
                encoded=obj(item[policy]);require(item['raw_bytes']==graph.sizes()[blob],'Canonical size differs')
                require(encoded[0] in (range(7) if policy=='adaptive' else (3,6)),'Invalid policy encoding mode')
                decode(encoded,item['raw_bytes'],blob);decoded_count+=1
        require(all(len(obj(item['adaptive']))<=len(obj(item['gzip9'])) for item in capture['payloads'].values()),
                'Adaptive encoding exceeds an available gzip choice')
    plans=json.loads((directory/'plans.json').read_bytes())
    cases={h+'/'+loss for h,loss in itertools.product(histories,config['losses'])}
    require(Counter((r['case'],r['method']) for r in plans)==Counter({key:1 for key in itertools.product(cases,config['methods'])}),
            'Missing, duplicate or replaced store plan')
    plan_index={(r['case'],r['method']):r for r in plans};faults={};sizes={};robustness={};targets={}
    for case in sorted(cases):
        history,loss=case.rsplit('/',1);graph=graphs[history];caps,k,_=capabilities(graph,loss)
        faults[case]=fault_sets(caps,k);sizes[case]={};robustness[case]={}
        targets[case]={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
        for method in config['methods']:
            record=plan_index[case,method];selected=set(record['selected'])
            require(len(selected)==len(record['selected']) and graph.roots<=selected<=graph.candidates,'Invalid selected artifacts')
            certs=[dict(disabled=list(lost),certificate=certificate(restricted(graph,caps,lost),selected)) for lost in faults[case]]
            complete=all(c['certificate']['complete'] for c in certs)
            require(record['certificates']==certs and record['robust']==complete,'Loss certificate differs')
            robustness[case][method]=complete
            if method in config['robust_methods']:require(complete,'Robust baseline cannot recover all declared losses')
            if method=='raw_exact':
                inventory={name:dict(bytes=len(raw),sha256=digest(raw)) for name,raw in {
                    'manifest.json':canonical(graph.manifest()),'capability_contract.json':contract(caps,k)}.items()}
                inventory.update({'blobs/'+b+'.pkl':dict(bytes=graph.sizes()[b],sha256=b) for b in selected})
            else:
                header=obj(record['metadata_object']);m=parse_metadata(header)
                require(m==dict(schema=1,format='lossless-per-file-v1',graph=graph.manifest(),contract=json.loads(contract(caps,k))),
                        'Encoded metadata changes the original preservation contract')
                policy='gzip9' if method=='gzip_exact' else 'adaptive'
                inventory={'metadata.rml':dict(bytes=len(header),sha256=digest(header))}
                inventory.update({'blobs/'+b+'.pkl':dict(bytes=len(obj(payloads[history][b][policy])),
                    sha256=payloads[history][b][policy]) for b in selected})
            require(record['inventory']==inventory and record['actual_bytes']==sum(i['bytes'] for i in inventory.values()),
                    'Measured store inventory or paid bytes differ')
            sizes[case][method]=record['actual_bytes']
        optional=sum(views[history]['adaptive'].sizes()[b] for b in set(plan_index[case,'adaptive_exact']['selected'])-graph.roots)
        for method in config['methods']:
            record=plan_index[case,method];require(record['optional_budget']==optional,'Shared optional budget differs')
            if method.startswith('HYPPO') or method=='HELIX_rule':
                require(sum(views[history]['adaptive'].sizes()[b] for b in set(record['selected'])-graph.roots)<=optional,'Adapter exceeded common byte budget')
        for method,view in [('raw_exact',graph),('gzip_exact',views[history]['gzip9']),('adaptive_exact',views[history]['adaptive'])]:
            chosen,status,diag=reference(view,caps,k,time_limit_s=config['solver_time_limit_s'])
            record=plan_index[case,method]
            require(status=='ok' and diag['storage_optimal'] and
                    sum(view.sizes()[b] for b in chosen)==sum(view.sizes()[b] for b in record['selected']),
                    'Independent exact objective differs')
            other=set(record['reference_selected'])
            require(sum(view.sizes()[b] for b in other)==sum(view.sizes()[b] for b in chosen) and
                    all(certificate(restricted(graph,caps,f),other)['complete'] for f in faults[case]),'Saved manual/reference optimum differs')
        require(plan_index[case,'adaptive_raw_choice']['selected']==plan_index[case,'raw_exact']['selected'],'Raw-choice control was replaced')
        require(set(plan_index[case,'adaptive_snapshots']['selected'])==graph.roots|targets[case],'Snapshot target set differs')
    trials=[json.loads(line) for line in gzip.decompress((directory/'trials.jsonl.gz').read_bytes()).splitlines()]
    check_grid(trials,cases,config['methods'],faults)
    for trial in trials:
        case,method=trial['case'],trial['method'];graph=graphs[case.rsplit('/',1)[0]];caps,k,_=capabilities(graph,case.rsplit('/',1)[1])
        plan=plan_index[case,method];selected=set(plan['selected'])
        expected=certificate(restricted(graph,caps,trial['disabled']),selected)['complete']
        found=trial['output_sha256'];valid=set(found)<=targets[case] and all(b==sha for b,sha in found.items())
        ok=trial['error'] is None and trial['receipt'] is not None and found=={b:b for b in targets[case]}
        blocked=not expected and trial['error'] is not None and 'No grounded alternative producer' in trial['error'] and valid
        unexpected=(expected and not ok) or (not expected and not blocked)
        require(trial['initial_outputs_empty'] and trial['expected_complete']==expected and trial['ok']==ok and
                trial['expected_blocked']==blocked and trial['unexpected']==unexpected and valid,'Request outcome classification differs')
        available=set(selected)
        for step in trial['operations']:
            if step['action']=='load':require(step['blob'] in selected,'Runtime loaded an omitted artifact')
            elif step['action']=='replay':
                producer=graph.nodes[step['producer']]
                require(caps.get(producer.id) not in trial['disabled'] and
                        {graph.nodes[d].blob for d in producer.deps}<=available,'Ungrounded or disabled producer executed')
                available.add(producer.blob)
        if ok:require(trial['receipt']['target_sha256']==found,'Receipt/target hashes differ')
    rows=json.loads((directory/'comparisons.json').read_bytes())
    require(len(rows)==len(cases) and {r['case'] for r in rows}==cases,'Comparison grid differs')
    for row in rows:
        case=row['case'];s=sizes[case]
        require(row['sizes']==s and row['saving_vs_raw']==1-s['adaptive_exact']/s['raw_exact'] and
                row['saving_vs_gzip']==1-s['adaptive_exact']/s['gzip_exact'] and
                row['saving_from_reselection']==1-s['adaptive_exact']/s['adaptive_raw_choice'] and
                row['manual_oracle_bytes']==s['adaptive_exact'],'Comparison summary differs')
    unexpected=sum(t['unexpected'] for t in trials)
    require(report['conditions']==len(cases) and report['requests']==len(trials) and report['unexpected']==unexpected and
            report['expected_blocks']==sum(t['expected_blocked'] for t in trials) and
            report['status']==('PASS' if unexpected==0 else 'FAIL'),'Block report differs')
    return dict(status=report['status'],dataset=dataset,recipe=recipe,smoke=smoke,source_commit=start['commit'],
        conditions=len(cases),requests=len(trials),unexpected=unexpected,expected_blocks=report['expected_blocks'],
        robust_requests=sum(t['method'] in config['robust_methods'] for t in trials),
        robust_exact=sum(t['method'] in config['robust_methods'] and t['ok'] for t in trials),
        decoded_candidate_files=decoded_count,target_hash_checks=sum(len(t['output_sha256']) for t in trials),
        methods={m:dict(requests=sum(t['method']==m for t in trials),exact=sum(t['method']==m and t['ok'] for t in trials),
            robust_conditions=sum(robustness[c][m] for c in cases)) for m in config['methods']},comparisons=rows,
        auditor_sha256=digest(Path(__file__).read_bytes()))


def complete(directory):
    config=json.loads((ROOT/'configs/encoded_storage_oct26.json').read_bytes())
    blocks=[block(Path(directory)/d/r) for d,r in itertools.product(config['datasets'],config['recipes'])]
    rows=[row for b in blocks for row in b['comparisons']]
    require(len({b['source_commit'] for b in blocks})==1 and len(rows)==config['expected_conditions'],'Full catalogue/source differs')
    require(sum(b['requests'] for b in blocks)==config['expected_requests'],'Full request denominator differs')
    strata={}
    for index,name in [(0,'dataset'),(1,'recipe'),(3,'loss')]:
        strata[name]={}
        for value in sorted({r['case'].split('/')[index] for r in rows}):
            subset=[r for r in rows if r['case'].split('/')[index]==value]
            wins=sum(r['saving_vs_raw']>=config['primary_gate']['minimum_saving_from_raw_exact'] for r in subset)
            strata[name][value]=dict(conditions=len(subset),substantial_raw_wins=wins,fraction=wins/len(subset),
                median_raw_saving=statistics.median(r['saving_vs_raw'] for r in subset),
                median_gzip_saving=statistics.median(r['saving_vs_gzip'] for r in subset))
    return dict(status='PASS' if all(b['status']=='PASS' for b in blocks) else 'FAIL',
        primary_gate_met=all(b['robust_requests']==b['robust_exact'] for b in blocks) and
          all(v['fraction']>=config['primary_gate']['minimum_fraction_each_dataset_recipe_loss'] for cells in strata.values() for v in cells.values()),
        source_commit=blocks[0]['source_commit'],conditions=len(rows),requests=sum(b['requests'] for b in blocks),
        robust_requests=sum(b['robust_requests'] for b in blocks),robust_exact=sum(b['robust_exact'] for b in blocks),
        unexpected=sum(b['unexpected'] for b in blocks),expected_blocks=sum(b['expected_blocks'] for b in blocks),
        decoded_candidate_files=sum(b['decoded_candidate_files'] for b in blocks),
        target_hash_checks=sum(b['target_hash_checks'] for b in blocks),strata=strata,
        methods={m:{k:sum(b['methods'][m][k] for b in blocks) for k in ('requests','exact','robust_conditions')} for m in config['methods']},
        blocks=blocks,qualification=config['scope'],auditor_sha256=digest(Path(__file__).read_bytes()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--smoke',action='store_true');parser.add_argument('--complete',action='store_true')
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    require(not args.complete or not args.preflight,'Full checks cannot bypass source identity')
    result=complete(args.directory) if args.complete else block(args.directory,args.smoke,args.preflight)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('blocks','comparisons')},indent=2))
