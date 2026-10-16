"""Independently reconcile fixed grids, flow proofs and actual recovery logs."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import itertools
import json
from pathlib import Path
import statistics
import tarfile
import tempfile

from recoverml.core import Graph, digest
from recoverml.capability_retention import retained_bytes
from recoverml.dag_retention import verify_proof


def grounded(g, selected, caps, lost):
    available = set(selected)
    while True:
        following = available | {n.blob for n in g.nodes.values() if n.replayable
            and caps.get(n.id) not in lost and all(g.nodes[d].blob in available for d in n.deps)}
        if following == available: return available
        available = following


def keys_match(actual, expected):
    counts = Counter(actual)
    if any(value != 1 for value in counts.values()) or set(counts) != set(expected):
        raise ValueError('Duplicate, missing or unexpected request identity')


def audit(directory):
    config = json.loads((directory/'protocol.json').read_text())
    end = json.loads((directory/'run_end.json').read_text())
    if end['status'] != 'PASS' or end['source_changed'] or end['errors']:
        raise ValueError('Run did not close cleanly')
    for path, expected in end['closed_evidence_sha256'].items():
        if digest((directory/path).read_bytes()) != expected:
            raise ValueError('Closed evidence changed: '+path)
    rows = list(csv.DictReader((directory/'summary.csv').open()))
    histories = {f'{data}-s{seed}-v{versions}-concat{int(concat)}': (data, seed, versions, concat)
                 for data, seed, versions, concat in itertools.product(config['datasets'], config['seeds'],
                                                       config['versions'], config['concat_materialized'])}
    expected_rows = {(h, m) for h in histories for m in config['methods']}
    keys_match([(r['history'], r['method']) for r in rows], expected_rows)
    temporary = None
    capture_base = directory
    if not (directory/'captures').is_dir():
        temporary = tempfile.TemporaryDirectory(prefix='recoverml_verify_captures_')
        capture_base = Path(temporary.name)
        with tarfile.open(directory/'captures.tar.gz') as archive:
            archive.extractall(capture_base, filter='data')
    graphs = {h: Graph.read(capture_base/'captures'/h/'manifest.json') for h in histories}
    caps = {h: {n.id: ('shared_standardization_entrypoint' if config.get('capture_input') else
               'preprocessing_view_'+str(index))
               for index, n in enumerate(n for n in g.nodes.values() if n.op=='view_standardize')}
            for h, g in graphs.items()}
    # Verify every captured physical byte against its content identity.
    payload_count = payload_bytes = 0
    for history, g in graphs.items():
        for blob in g.candidates:
            raw = (capture_base/'captures'/history/'blobs'/(blob+'.pkl')).read_bytes()
            if digest(raw) != blob or len(raw) != g.sizes()[blob]:
                raise ValueError('Capture payload mismatch')
            payload_count += 1; payload_bytes += len(raw)
    archive_files = 0
    with tarfile.open(directory/'captures.tar.gz') as archive:
        for member in archive.getmembers():
            if member.isfile():
                raw = archive.extractfile(member).read()
                if raw != (capture_base/member.name).read_bytes():
                    raise ValueError('Capture archive differs from checked capture')
                archive_files += 1
    plans = json.loads(gzip.decompress((directory/'planner_records.json.gz').read_bytes()))
    keys_match([(p['history'],p['method'],p['repetition']) for p in plans],
               {(h,m,r) for h,m,r in itertools.product(histories,config['methods'],range(config['timing_repetitions']))})
    selections = {}; proofs = 0
    for plan in plans:
        h, method = plan['history'], plan['method']; g=graphs[h]; selected=set(plan['selected'])
        if not g.roots <= selected <= g.candidates: raise ValueError('Invalid selected set')
        if retained_bytes(g,selected,caps[h],1) != plan['retained_bytes']: raise ValueError('Planner byte count mismatch')
        if method=='RecoverML_exact':
            verify_proof(g,caps[h],1,selected,plan['detail']['proof']); proofs+=1
        identity=(h,method)
        if identity in selections and selections[identity]!=selected: raise ValueError('Selection instability')
        selections[identity]=selected
    stores={}; row_index={}
    for row in rows:
        h,method=row['history'],row['method'];g=graphs[h];s=selections[(h,method)]
        key=digest('\n'.join(sorted(s)).encode())
        if row['store_key']!=key: raise ValueError('Store key mismatch')
        if retained_bytes(g,s,caps[h],1)!=int(row['retained_bytes']):raise ValueError('Summary bytes mismatch')
        allowed = [()] + [(group,) for group in sorted(set(caps[h].values()))]
        robust = all(all(g.nodes[t].blob in grounded(g,s,caps[h],lost)
                         for ts in g.targets.values() for t in ts) for lost in allowed)
        if (row['fully_recoverable']=='True') != robust:raise ValueError('Summary robustness differs from independent closure')
        if method in ('HYPPO_rank','HYPPO_frequency','HELIX_rule') and int(row['retained_bytes']) > int(row['exact_minimum_bytes']):
            raise ValueError('Published materializer exceeded common minimum budget')
        stores[(h,key)]=s;row_index[(h,method)]=row
    expected={}; runtime=Counter(); times=defaultdict(list); operations=0; execution_records=[]
    for (h,key), selected in stores.items():
        g=graphs[h];groups=sorted(set(caps[h].values()));faults=[()]+[(group,) for group in groups]
        for lost in faults:
            available=grounded(g,selected,caps[h],lost)
            for version,targets in g.targets.items():
                expected[(h,key,tuple(lost),version)]=all(g.nodes[t].blob in available for t in targets)
    identities=[]; store_counts=defaultdict(Counter)
    with gzip.open(directory/'execution_traces.jsonl.gz','rt') as handle:
        for line in handle:
            r=json.loads(line);h=r['history'];key=r['store_key'];lost=tuple(r['disabled'])
            identity=(h,key,lost,r['version']);identities.append(identity)
            if identity not in expected or type(r['exact']) is not bool or type(r['expected_recoverable']) is not bool:
                raise ValueError('Unexpected identity or invalid outcome type')
            if expected[identity] != r['expected_recoverable'] or expected[identity] != r['exact']:
                raise ValueError('Runtime outcome differs from independent closure')
            if r['exact'] and r['error'] is not None:raise ValueError('Successful request has error')
            g=graphs[h];targets=g.targets[r['version']]
            if r['target_sha256'] != [g.nodes[t].blob for t in targets]:raise ValueError('Wrong target hash list')
            for op in r['operations']:
                operations+=1
                if not op['exact']:raise ValueError('Operation not exact')
                if op['producer'] is not None and caps[h].get(op['producer']) in lost:
                    raise ValueError('Disabled operator dispatched')
            runtime['requests']+=1;runtime['exact']+=int(r['exact'])
            runtime['expected_blocked']+=int(not r['exact']);runtime['unexpected']+=0
            store_counts[(h,key)]['exact' if r['exact'] else 'expected_blocked']+=1
            store_counts[(h,key)]['requests']+=1;times[(h,key)].append(r['elapsed_s'])
    keys_match(identities,expected)
    if dict(runtime)!=end['actual_runtime']:raise ValueError('End counters differ from raw traces')
    for row in rows:
        count=store_counts[(row['history'],row['store_key'])]
        for name in ('exact','expected_blocked','requests'):
            if int(row[name])!=count[name]:raise ValueError('Summary request counters differ')
    # Mutation checks use the same request identity validation as this audit.
    accepted_reordered=False
    keys_match(list(reversed(identities)),expected);accepted_reordered=True
    rejected=[]
    for name, changed in [('duplicate',identities+[identities[0]]),('missing',identities[:-1]),
                          ('replacement_duplicate',identities[:-1]+[identities[0]])]:
        try:keys_match(changed,expected)
        except ValueError:rejected.append(name)
        else:raise ValueError('Mutation control unexpectedly accepted')
    comparisons=[]
    for h,(data,seed,versions,concat) in histories.items():
        ours=row_index[(h,'RecoverML_exact')];local=row_index[(h,'robust_local')]
        manual=row_index[(h,'manual_best_frontier')];reference=row_index[(h,'scenario_exact')]
        if int(ours['retained_bytes']) != int(reference['retained_bytes']):raise ValueError('Exact disagreement')
        comparisons.append(dict(history=h,dataset=data,seed=seed,versions=versions,concat_materialized=concat,
            our_bytes=int(ours['retained_bytes']),local_bytes=int(local['retained_bytes']),manual_bytes=int(manual['retained_bytes']),
            saved_vs_local=int(local['retained_bytes'])-int(ours['retained_bytes']),
            percent_vs_local=100*(int(local['retained_bytes'])-int(ours['retained_bytes']))/int(local['retained_bytes']),
            planning_speedup_vs_local=float(local['planning_median_s'])/float(ours['planning_median_s']),
            planning_speedup_vs_scenario=float(reference['planning_median_s'])/float(ours['planning_median_s'])))
    report=dict(status='PASS',histories=len(histories),conditions=len(rows),planning_calls=len(plans),
        checked_flow_proofs=proofs,captured_payloads=payload_count,captured_payload_bytes=payload_bytes,
        checked_capture_archive_files=archive_files,unique_stores=len(stores),actual_runtime=dict(runtime),
        checked_runtime_operations=operations,reordered_trace_accepted=accepted_reordered,rejected_mutations=rejected,
        comparisons=comparisons,all_exact_formulations_agree=True,
        qualification='Exploratory constructed histories and declared fault groupings; no claim of independent confirmation or universal superiority')
    (directory/'independent_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    if temporary is not None:temporary.cleanup()
    return report


def plot(directory, report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    comparisons=report['comparisons'];fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for dataset,color in [('wine','#1f77b4'),('breast_cancer','#d95f02')]:
        for concat,style in [(False,'-'),(True,'--')]:
            selected=[r for r in comparisons if r['dataset']==dataset and r['concat_materialized']==concat]
            xs=sorted({r['versions'] for r in selected})
            label=dataset.replace('_',' ')+(' with concat' if concat else ' fused')
            axes[0].plot(xs,[statistics.median(r['percent_vs_local'] for r in selected if r['versions']==x) for x in xs],
                style,marker='o',color=color,label=label)
            axes[1].plot(xs,[statistics.median(r['planning_speedup_vs_local'] for r in selected if r['versions']==x) for x in xs],
                style,marker='o',color=color,label=label)
    axes[0].set(ylabel='Storage reduction versus strong local search (%)',xlabel='Historical model versions',xticks=[4,16,64])
    axes[1].set(ylabel='Planning speedup versus strong local search (times)',xlabel='Historical model versions',yscale='log',xticks=[4,16,64])
    for axis in axes:axis.grid(alpha=.25);axis.axhline(0 if axis==axes[0] else 1,color='gray',linewidth=.7)
    axes[0].legend(fontsize=8)
    fig.suptitle('Exploratory two-view workflows — medians over three split seeds')
    fig.savefig(directory/'strong_baseline_comparison.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();report=audit(args.directory);plot(args.directory,report)
    print(json.dumps({k:v for k,v in report.items() if k!='comparisons'},indent=2))
