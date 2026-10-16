#!/usr/bin/env python3
"""Independent full-grid reconciliation for the fixed GB-scale letter study."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

from recoverml.core import Graph, canonical, digest
from recoverml.capability_retention import contract, retained_bytes, restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate

METHODS={'RecoverML_exact','scenario_exact','robust_greedy','robust_local','target_snapshots'}


def load(path):
    return json.loads(path.read_text())


def stream_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):
            h.update(data)
    return h.hexdigest()


def analyze(output, work=None):
    config=load(output/'protocol.json');capture=load(output/'capture_inventory.json')
    report=load(output/'report.json');plans=load(output/'planner_records.json')
    inventory=load(output/'blob_inventory.json');stores=load(output/'runtime_store_index.json')
    graph=Graph.read(output/'manifest.json');errors=[]
    def check(condition,message):
        if not condition:
            errors.append(message)
    expected_models=len(config['configurations'])
    check(len(capture['models'])==expected_models,'Incomplete configured model grid')
    check(capture['selected_configurations']==config['configurations'],'Configuration grid changed')
    check([m['parameters'] for m in capture['models']]==[dict(c,n_jobs=1) for c in config['configurations']],'Actual fitted model parameters differ')
    check(capture['rows']==20000 and capture['train_rows']==15000 and capture['test_rows']==5000,'Dataset/split dimensions differ')
    check(capture['transformed_features']==12 and capture['training_partition_only_fit'],'Preprocessing protocol differs')
    check(len({m['model_blob'] for m in capture['models']})==expected_models,'Duplicate model blobs')
    check(set(graph.targets)=={str(v) for v in range(expected_models)},'Historical target grid differs')
    check(set(inventory)==graph.candidates,'Physical blob ledger differs from manifest')
    check(all(inventory[b]['bytes']==graph.sizes()[b] for b in inventory),'Manifest payload sizes differ')
    expected={(scope,method) for scope in config['capability_scopes'] for method in METHODS}
    keys=[(p['scope'],p['policy']) for p in plans]
    check(set(keys)==expected and len(keys)==len(expected),'Missing or duplicate scope/policy cases')
    with (output/'summary.csv').open() as stream:
        summaries=list(csv.DictReader(stream))
    check(Counter((r['scope'],r['policy']) for r in summaries)==Counter(keys),'Summary case grid differs')
    structural=[]
    target_blobs={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    snapshot=graph.roots|target_blobs
    for plan in plans:
        selected=set(plan['selected']);caps=plan['capabilities'];scope=plan['scope'];method=plan['policy']
        check(selected<=graph.candidates and graph.roots<=selected,f'Invalid selected set {scope}/{method}')
        check(plan['selected_sha256']==digest(canonical(sorted(selected))),f'Selected set hash differs {scope}/{method}')
        check(retained_bytes(graph,selected,caps,1)==plan['retained_bytes'],f'Uncompressed byte accounting differs {scope}/{method}')
        check(graph.metadata_bytes()+len(contract(caps,1))+sum(inventory[b]['gzip_bytes'] for b in selected)==plan['compressed_retained_bytes'],f'Gzip byte accounting differs {scope}/{method}')
        check(plan['retained_bytes']<=plan['budget_bytes'],f'Budget exceeded {scope}/{method}')
        count=total=0
        for lost in fault_sets(caps,1):
            result=certificate(restricted(graph,caps,lost),selected)
            for version,ok in result['version_coverage'].items():
                structural.append(dict(scope=scope,policy=method,version=version,disabled=list(lost),recoverable=ok))
                count+=int(ok);total+=1
        check(count==plan['allowed_structural_exact'] and total==plan['allowed_structural_requests'],f'Allowed-scenario certificate mismatch {scope}/{method}')
        # Heuristics may be partial at this byte budget. This is an outcome,
        # not a reason to reject an otherwise valid experiment record.
        if method in {'RecoverML_exact','scenario_exact'}:
            check(plan['status']=='ok' and plan['diagnostic'].get('storage_optimal') and plan['diagnostic'].get('robust_certified'),f'Uncertified exact result {scope}/{method}')
            check(count==total,f'Exact method fails allowed contract {scope}/{method}')
    saved_structural=load(output/'allowed_scenario_certificates.json')
    # Canonical JSON sorts version keys lexicographically whereas capture
    # records follow numeric insertion order. Check full records and their
    # multiplicities rather than treating serialization order as semantics.
    check(Counter(canonical(row) for row in structural)==Counter(canonical(row) for row in saved_structural),
          'Saved structural certificate ledger differs')
    saved_keys=[(row['scope'],row['policy'],row['version'],tuple(row['disabled'])) for row in saved_structural]
    check(len(saved_keys)==len(set(saved_keys)),'Duplicate saved structural request identity')
    for scope in config['capability_scopes']:
        exacts=[p['retained_bytes'] for p in plans if p['scope']==scope and p['policy'] in {'RecoverML_exact','scenario_exact'}]
        check(len(exacts)==2 and len(set(exacts))==1,f'Independent exact optima disagree for {scope}')
    traces=[]
    with gzip.open(output/'execution_traces.jsonl.gz','rt') as stream:
        traces=[json.loads(line) for line in stream]
    trace_keys=[(r['runtime_key'],r['version']) for r in traces]
    check(len(trace_keys)==len(set(trace_keys)),'Duplicate actual runtime request')
    check(set(trace_keys)=={(key,str(v)) for key in stores for v in range(expected_models)},'Actual runtime request grid differs')
    for key,store in stores.items():
        rows=[r for r in traces if r['runtime_key']==key]
        check(store['selected_sha256']==digest(canonical(store['selected'])),f'Runtime selected-set hash differs {key}')
        check(key==digest(canonical(dict(selected=store['selected'],disabled=store['disabled']))),f'Runtime identity differs {key}')
        check(len(rows)==store['actual_requests']==expected_models,f'Incomplete runtime versions {key}')
        check(sum(r['exact'] for r in rows)==store['exact'] and sum(r['expected_blocked'] for r in rows)==store['expected_blocked'],'Runtime count differs')
        check(sum(r['unexpected'] for r in rows)==store['unexpected']==0,'Unexpected recovery failure')
        for row in rows:
            check(row['capture_archive_empty'] and row['stress_exceeds_k1'],'Runtime scope qualification missing')
            check(row['exact'] or row['expected_blocked'],'Unclassified recovery request')
            check(row['end_timestamp_ns']>=row['start_timestamp_ns'] and row['elapsed_s']>=0,'Invalid raw timing')
            if row['exact']:
                materialized={event['blob'] for event in row['events']}
                check({graph.nodes[t].blob for t in graph.targets[row['version']]}<=materialized,'Exact request omits a target event')
    check(report['actual_runtime_requests']==len(traces),'Report inflated actual runtime count')
    check(report['actual_runtime_exact']==sum(r['exact'] for r in traces),'Report exact count differs')
    check(not report['source_changed_during_run'],'Sources changed during run')
    dvc=load(output/'native_dvc_report.json');commands=load(output/'native_dvc_commands.json')
    expected_dvc={b+'.pkl':dict(sha256=b,bytes=graph.sizes()[b]) for b in target_blobs}
    check(dvc['status']=='PASS' and dvc['missing_before_checkout'],'Native DVC checkout control failed')
    check(dvc['expected']==dvc['actual']==expected_dvc,'Native DVC did not verify every target file')
    check(dvc['physical_files_checked']==len(expected_dvc),'Native DVC file count differs')
    check(len(commands)==4 and all(c['returncode']==0 for c in commands),'Native DVC command receipts differ')
    if work:
        for blob,item in inventory.items():
            raw=work/'capture_blobs'/(blob+'.pkl');zipped=work/'gzip_blobs'/(blob+'.pkl.gz')
            check(raw.exists() and raw.stat().st_size==item['bytes'] and stream_hash(raw)==blob,'Actual raw payload differs: '+blob)
            check(zipped.exists() and zipped.stat().st_size==item['gzip_bytes'] and stream_hash(zipped)==item['gzip_sha256'],'Actual gzip payload differs: '+blob)
            h=hashlib.sha256();count=0
            with gzip.open(zipped,'rb') as stream:
                for data in iter(lambda:stream.read(1024*1024),b''):
                    h.update(data);count+=len(data)
            check(h.hexdigest()==blob and count==item['bytes'],'Gzip content does not reproduce exact artifact '+blob)
        for model in capture['models']:
            native=work/'native_pickle'/(str(model['version'])+'.pkl')
            zipped=work/'native_pickle'/(str(model['version'])+'.pkl.gz')
            check(native.stat().st_size==model['native_pickle_bytes'] and stream_hash(native)==model['native_pickle_sha256'],'Native pickle diagnostic differs')
            check(zipped.stat().st_size==model['native_gzip_bytes'] and stream_hash(zipped)==model['native_gzip_sha256'],'Native gzip diagnostic differs')
    by_scope={}
    for scope in config['capability_scopes']:
        optimum=next(p for p in plans if p['scope']==scope and p['policy']=='RecoverML_exact')
        caps=optimum['capabilities'];baseline=retained_bytes(graph,snapshot,caps,1)
        gzip_base=graph.metadata_bytes()+len(contract(caps,1))+sum(inventory[b]['gzip_bytes'] for b in snapshot)
        predictions={m['prediction_blob'] for m in capture['models']}
        native_base=graph.metadata_bytes()+len(contract(caps,1))+sum(inventory[b]['bytes'] for b in graph.roots|predictions)+sum(m['native_pickle_bytes'] for m in capture['models'])
        native_gzip_base=graph.metadata_bytes()+len(contract(caps,1))+sum(inventory[b]['gzip_bytes'] for b in graph.roots|predictions)+sum(m['native_gzip_bytes'] for m in capture['models'])
        by_scope[scope]=dict(snapshot_bytes=baseline,exact_bytes=optimum['retained_bytes'],saving_bytes=baseline-optimum['retained_bytes'],
            saving_percent=100*(baseline-optimum['retained_bytes'])/baseline,
            gzip_snapshot_bytes=gzip_base,gzip_exact_bytes=optimum['compressed_retained_bytes'],
            gzip_saving_bytes=gzip_base-optimum['compressed_retained_bytes'],
            native_pickle_snapshot_bytes=native_base,native_pickle_snapshot_minus_canonical_frontier_bytes=native_base-optimum['retained_bytes'],
            native_gzip_snapshot_bytes=native_gzip_base,native_gzip_snapshot_minus_gzip_frontier_bytes=native_gzip_base-optimum['compressed_retained_bytes'],
            planning_s=optimum['planning_s'],
            qualification='The native representation controls use native model pickles and common canonical roots/predictions; canonical and native byte identities differ')
    result=dict(status='PASS' if not errors else 'FAIL',errors=errors,models=expected_models,case_rows=len(plans),
       unique_runtime_stores=len(stores),actual_runtime_requests=len(traces),actual_exact=sum(r['exact'] for r in traces),
       actual_expected_blocked=sum(r['expected_blocked'] for r in traces),actual_unexpected=sum(r['unexpected'] for r in traces),
       allowed_structural_requests=len(structural),allowed_structural_exact=sum(r['recoverable'] for r in structural),
       payload_files_verified=bool(work), native_dvc_files_verified=len(expected_dvc),
       scopes=by_scope,uncompressed_1GB_goal_met=by_scope['preprocessing']['saving_bytes']>=1_000_000_000,
       gzip_1GB_goal_met=by_scope['preprocessing']['gzip_saving_bytes']>=1_000_000_000,
       interpretation='A storage result for a declared failure scope; not proof of novelty, universal baseline superiority, or production prevalence')
    (output/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    write_results(output,result,plans,capture)
    return result


def write_results(output,result,plans,capture):
    lines=['# Fixed UCI Letter history storage experiment','',
      'All 20,000 observations are used and preprocessing is fitted only on 15,000 training observations and predictions are evaluated on 5,000 held-out observations.',
      'This is an executable constructed hyperparameter tuning history with genuine trained forests and no padding or duplicate model payloads.',
      '',f"Validation: **{result['status']}** and {result['models']} actual trained model versions.",
      f"Actual replay requests: {result['actual_runtime_requests']} and exact: {result['actual_exact']} and expected blocked: {result['actual_expected_blocked']} and unexpected: {result['actual_unexpected']}.",
      'Replay uses every version under all preprocessing groups disabled which is a stronger stress than the allowed k=1 contract and the k=1 claims are checked separately by complete structural enumeration.',
      'Methods with identical selected payloads share runtime evidence and those requests are counted once.',
      '', '| Scope | Snapshot bytes | RecoverML bytes | Saved bytes | Gzip saved bytes |', '|---|---:|---:|---:|---:|']
    for scope,r in result['scopes'].items():
        lines.append(f"| {scope} | {r['snapshot_bytes']:,} | {r['exact_bytes']:,} | {r['saving_bytes']:,} | {r['gzip_saving_bytes']:,} |")
    lines+=['','| Scope | Method | Retained bytes | Complete allowed requests | Planning seconds |', '|---|---|---:|---:|---:|']
    for p in plans:
        lines.append(f"| {p['scope']} | {p['policy']} | {p['retained_bytes']:,} | {p['allowed_structural_exact']}/{p['allowed_structural_requests']} | {p['planning_s']:.6f} |")
    lines+=['','Accuracy range: '+str(min(m['accuracy'] for m in capture['models']))+' to '+str(max(m['accuracy'] for m in capture['models'])),
      '', 'The uncompressed canonical model identity is the main contract and gzip level 6 is measured on every actual payload. The separate native sklearn pickle control is included in analysis.json because canonical JSON/base64 serialization can be substantially larger than native pickle.',
      'A GB reduction in uncompressed canonical bytes does not imply a GB reduction in compressed files. Both outcomes are reported separately.',
      'A simple manual choice of a shared recoverable feature frontier can match an exact optimizer on this workflow and this experiment alone does not prove that optimization is necessary.',
      'Native DVC is tested with actual add and deletion and checkout and every unique target file hash is checked. DVC command startup is separate from in-process recovery timing.',
      'The broad-failure condition is retained even when it saves no storage because training or prediction loss can require their target snapshots.',
      'One CPU host and one replay per unique store and version are used and histories share a dataset so raw requests are not independent statistical samples.',
      '', 'Raw large payloads are reproducible from the fixed source and protocol but are not committed. The small exact preprocessing frontier and all selected-set identities and command receipts are included.']
    (output/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,len(result['scopes']),figsize=(12,4.8),squeeze=False)
    for axis,(scope,_) in zip(axes[0],result['scopes'].items()):
        chosen=[p for p in plans if p['scope']==scope]
        axis.bar(range(len(chosen)),[p['retained_bytes']/1e9 for p in chosen],color=['#16758c','#748ba3','#bf8957','#859d52','#666666'])
        axis.set_xticks(range(len(chosen)),[p['policy'].replace('_','\n') for p in chosen],fontsize=8)
        axis.set_ylabel('Retained storage (decimal GB)');axis.set_title(scope+' capability loss and k=1')
        axis.grid(axis='y',alpha=.2);axis.set_axisbelow(True)
    fig.suptitle('Fixed UCI Letter model history and canonical artifact bytes')
    fig.tight_layout();fig.savefig(output/'storage_comparison.png',dpi=180);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--verify-payloads',type=Path)
    args=p.parse_args();answer=analyze(args.output,args.verify_payloads);print(json.dumps(answer,indent=2));sys.exit(0 if answer['status']=='PASS' else 1)
