"""Audit complete census blocks, including failures, cache budget and all strata."""
import argparse
from collections import Counter
import itertools
import json
import math
import random
from pathlib import Path
import statistics
import subprocess
import tarfile
import yaml

from recoverml.core import Graph,Node,digest
from recoverml.capability_retention import retained_bytes,restricted
from recoverml.scenario_retention import optimize as reference
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate
from recoverml.broad_workflows import capabilities
from benchmark_recovery_census import ROOT,catalogue


def require(ok,message):
    if not ok:raise ValueError(message)


def members(path):
    with tarfile.open(path) as archive:
        files=[m for m in archive if m.isfile()]
        require(len(files)==len({m.name for m in files}),'Duplicate archive member')
        return {m.name:archive.extractfile(m).read() for m in files}


def read_graph(raw):
    m=json.loads(raw);g=Graph(env=m['environment'])
    g.nodes={n['id']:Node(**n) for n in m['nodes']}
    g.targets=m['targets'];g.roots=set(m['mandatory_blobs'])
    return g


def trial_grid(trials,cases,methods,repetitions):
    expected=Counter({key:1 for key in itertools.product(cases,methods,range(repetitions))})
    require(Counter((r['case'],r['method'],r['repetition']) for r in trials)==expected,
            'Missing/duplicate/replaced trial')


def block(directory,smoke=False):
    start=json.loads((directory/'run_start.json').read_bytes())
    report=json.loads((directory/'report.json').read_bytes())
    config=json.loads((ROOT/'configs/recovery_census_oct26.json').read_bytes())
    if smoke:config=dict(config,versions=[1],repetitions=1)
    require(start['smoke']==smoke and start['config']==config,'Protocol or smoke classification differs')
    require(not report['source_changed'],'Runtime source changed')
    archived=members(directory/'source_snapshot.tar.gz')
    source_paths=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',start['commit'],
                                         'src/recoverml'],text=True).splitlines()
    expected_sources={p for p in source_paths if p.endswith('.py')} | {
        'scripts/benchmark_recovery_census.py','scripts/broad_recovery_worker.py',
        'scripts/native_frontier_worker.py','configs/recovery_census_oct26.json'}
    require(set(start['source_sha256'])==expected_sources,'Pinned source inventory incomplete')
    require(set(archived)==set(start['source_sha256']),'Source inventory differs')
    for path,sha in start['source_sha256'].items():
        require(digest(archived[path])==sha,'Archived source differs')
        raw=subprocess.check_output(['git','-C',str(ROOT),'show',start['commit']+':'+path])
        require(raw==archived[path],'Source differs from recorded commit')
    for path,sha in report['closed_sha256'].items():
        require(digest((directory/path).read_bytes())==sha,'Closed evidence differs')
    captures=members(directory/'captures.tar.gz')
    native_cases=members(directory/'cases.tar.gz')
    dataset,recipe=start['dataset'],start['recipe']
    graphs={}
    for versions in config['versions']:
        history=f'{dataset}-{recipe}-v{versions}'
        raw=captures['captures/'+history+'/manifest.json'];g=read_graph(raw)
        graphs[history]=g
        for blob in g.candidates:
            raw=captures['captures/'+history+'/blobs/'+blob+'.pkl']
            require(digest(raw)==blob and len(raw)==g.sizes()[blob],'Captured payload differs')
    retentions=json.loads((directory/'retentions.json').read_bytes())
    expected_retention={f'{dataset}-{recipe}-v{v}-{loss}-{request}'
                        for v,loss,request in itertools.product(config['versions'],config['losses'],config['requests'])}
    require(set(retentions)==expected_retention,'Incomplete retention grid')
    for key,r in retentions.items():
        g=graphs[r['history']];loss=key.split('-')[-2]
        caps,k,disabled=capabilities(g,loss)
        require(r['capabilities']==caps and r['k']==k and r['disabled']==disabled,'Loss contract differs')
        selected=set(r['selected'])
        stage=yaml.safe_load(native_cases['cases/'+key+'/dvc.yaml'])['stages']['recover_requested']
        expected_outs={'outputs/'+g.nodes[t].blob+'.pkl' for t in r['targets']}
        require(set(stage['outs'])==expected_outs,'Native stage performs extra or missing target work')
        require(g.roots<=selected<=g.candidates,'Invalid selected set')
        size=retained_bytes(g,selected,caps,k)
        require(size==r['common_bytes'],'Paid storage differs')
        require(all(certificate(restricted(g,caps,f),selected)['complete'] for f in fault_sets(caps,k)),
                'Selected store is not robust')
        chosen,status,diag=reference(g,caps,k,time_limit_s=120.)
        require(status=='ok' and diag['storage_optimal'] and retained_bytes(g,chosen,caps,k)==size,
                'Independent exact formulation differs')
    trials=[json.loads(line) for line in (directory/'trials.jsonl').read_text().splitlines() if line]
    cases=catalogue(config,dataset,recipe)
    trial_grid(trials,cases,config['methods'],config['repetitions'])
    require(len(trials)==report['trials'],'Trial total differs')
    require(report['status']==('PASS' if all(r['ok'] for r in trials) else 'FAIL'),'Outcome status differs')
    commands=[json.loads(line) for line in (directory/'commands.jsonl').read_text().splitlines() if line]
    command_index={r['label']:r for r in commands}
    require(len(command_index)==len(commands),'Duplicate command identity')
    rows={r['case']:r for r in report['comparisons']}
    require(set(rows)==set(cases) and len(rows)==len(report['comparisons']),'Incomplete comparison grid')
    exact_targets=0
    for case in cases:
        parts=case.split('/');versions=int(parts[2][1:]);loss,request,interface=parts[3:]
        history=f'{dataset}-{recipe}-v{versions}';g=graphs[history]
        key=f'{history}-{loss}-{request}';retention=retentions[key]
        ids=(list(g.targets[str(versions-1)]) if request=='latest' else
             list(dict.fromkeys(t for ts in g.targets.values() for t in ts)))
        require(retention['targets']==ids,'Requested target set differs')
        targets={g.nodes[t].blob for t in ids};selected=set(retention['selected'])
        current=[r for r in trials if r['case']==case]
        for repetition in range(config['repetitions']):
            order=list(config['methods']);random.Random(case+str(repetition)).shuffle(order)
            require(sorted((r['order'],r['method']) for r in current if r['repetition']==repetition)
                    ==list(enumerate(order)),'Paired method order differs')
        for trial in current:
            require(trial['retention_key']==key and set(trial['initial_payloads'])==selected,'Initial store differs')
            require(trial['outputs_initially_empty'] and set(trial['cache_sha256'])<=selected,'Hidden output/cache')
            paid=sum(g.sizes()[b] for b in selected)
            require(trial['paid_payload_bytes']==trial['unique_initial_payload_bytes']==paid,'Physical byte budget differs')
            require(math.isfinite(trial['elapsed_s']) and trial['elapsed_s']>=0,'Invalid elapsed time')
            if trial['ok']:
                require(trial['target_sha256']=={b:b for b in targets} and trial['error'] is None,'Target hashes differ')
                exact_targets+=len(targets)
                require(trial['worker_receipt'] is not None or
                        (trial['method']=='DVC_native' and targets<=selected),'Missing successful replay receipt')
            else:
                require(trial['error'] is not None,'Failure has no error receipt')
            if trial['method']=='DVC_native':
                require(trial['native_action']==('checkout' if targets<=selected else 'repro'),'Weak native command choice')
            if interface=='cli':
                command=command_index[case+':'+trial['method']+':'+str(trial['repetition'])]
                require(trial['elapsed_s']>=command['elapsed_s'],'Timing shorter than command')
                require((command['returncode']==0) or not trial['ok'],'Failed command labelled exact')
            for step in trial['operations']:
                node=step.get('producer',step.get('node'))
                if step['action']=='replay':
                    require(node in g.nodes and retention['capabilities'].get(node) not in retention['disabled'],
                            'Disabled producer executed')
        medians={m:statistics.median(r['elapsed_s'] for r in current if r['method']==m) for m in config['methods']}
        exact={m:all(r['ok'] for r in current if r['method']==m) for m in config['methods']}
        ratio=medians['DVC_native']/medians['RecoverML']
        require(rows[case]['median_s']==medians and rows[case]['exact']==exact
                and rows[case]['ratio_dvc_to_recoverml']==ratio
                and rows[case]['substantial_win']==(all(exact.values()) and ratio>=config['success']['minimum_case_speedup'])
                and rows[case]['all_requested_retained']==(targets<=selected),'Raw/summary link differs')
    return dict(dataset=dataset,recipe=recipe,source_commit=start['commit'],smoke=smoke,
        comparisons=list(rows.values()),trials=len(trials),exact_trials=sum(r['ok'] for r in trials),
        target_hash_checks=exact_targets,unexpected_failures=sum(not r['ok'] for r in trials),
        auditor_sha256=digest(Path(__file__).read_bytes()))


def complete(directory):
    config=json.loads((ROOT/'configs/recovery_census_oct26.json').read_bytes())
    blocks=[];rows=[]
    for dataset,recipe in itertools.product(config['datasets'],config['recipes']):
        r=block(directory/dataset/recipe)
        blocks.append(r);rows.extend(r['comparisons'])
    require(len({r['source_commit'] for r in blocks})==1,'Blocks used different source commits')
    require(len(rows)==config['expected_comparisons'],'Catalogue denominator differs')
    strata={}
    for column,name in [(0,'dataset'),(1,'recipe'),(3,'loss'),(4,'request'),(5,'interface')]:
        strata[name]={}
        for value in sorted({r['case'].split('/')[column] for r in rows}):
            subset=[r for r in rows if r['case'].split('/')[column]==value]
            wins=sum(r['substantial_win'] for r in subset)
            strata[name][value]=dict(cases=len(subset),substantial_wins=wins,fraction=wins/len(subset),
                median_dvc_to_recoverml=statistics.median(r['ratio_dvc_to_recoverml'] for r in subset),
                median_direct_to_recoverml=statistics.median(r['median_s']['direct_control']/r['median_s']['RecoverML'] for r in subset))
    failures=sum(r['unexpected_failures'] for r in blocks)
    meets=(failures==0 and all(v['fraction']>=config['success']['minimum_win_fraction_each_interface']
                               for v in strata['interface'].values())
           and all(v['fraction']>=config['success']['minimum_win_fraction_each_stratum']
                   for cells in strata.values() for v in cells.values()))
    return dict(status='PASS' if failures==0 else 'FAIL',success_criteria_met=meets,
        source_commit=blocks[0]['source_commit'],comparisons=len(rows),trials=sum(b['trials'] for b in blocks),
        exact_trials=sum(b['exact_trials'] for b in blocks),unexpected_failures=failures,
        target_hash_checks=sum(b['target_hash_checks'] for b in blocks),strata=strata,blocks=blocks,
        qualification=config['scope'],auditor_sha256=digest(Path(__file__).read_bytes()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--complete',action='store_true');parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    result=complete(args.directory) if args.complete else block(args.directory,args.smoke)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('blocks','comparisons')},indent=2))
