"""Reconcile complete original histories and all prospectively rerun forest cases.

Nothing is inferred from outcome to decide what enters the fixed denominator.
The original unfinished CSV and compressed trace are never changed.
"""
import argparse
import csv
import gzip
import itertools
import json
import shutil
from pathlib import Path
import sys
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from recoverml.core import Graph,digest,environment
from recoverml.scientific_workflows import caps_for
from recoverml.capability_retention import retained_bytes
from recoverml.component_retention import optimize as exact
from recoverml.scenario_retention import optimize as reference
from recoverml.scientific_benchmarks import dump
from resume_scientific_matrix import readable_records,request_identity,select_complete_original
from threadpoolctl import threadpool_limits


def merge(original,resumed,destination):
    destination.mkdir(parents=True,exist_ok=False)
    resume=json.loads((resumed/'resume_protocol.json').read_text())
    protocol=json.loads((resumed/'protocol.json').read_text())
    for key,name in [('original_summary_sha256','summary.csv'),('original_trace_sha256','execution_traces.jsonl.gz')]:
        if digest((original/name).read_bytes())!=resume[key]:raise RuntimeError('Original evidence changed')
    original_rows=list(csv.DictReader((original/'summary.csv').open()))
    original_raw,truncation=readable_records(original/'execution_traces.jsonl.gz')
    histories,rows,traces,selection=select_complete_original(protocol,original,original_rows,original_raw,resume['reused_workflows'])
    plans=[];sensitivity=[];captures=[];failures=[];case_receipts=[];start=time.time_ns()
    for history in histories:
        info=json.loads((original/'captures'/history/'capture_info.json').read_text())
        captures.append(dict(history=history,capture_s=None,capture_timing='Not checkpointed before interruption',**info))
    dump(destination/'protocol.json',protocol);dump(destination/'resume_protocol.json',resume)
    # The old timed planning ledgers were in memory at interruption. Recompute
    # only feasibility/minimum certificates, never substitute these for old times.
    with threadpool_limits(limits=1):
        for history,scope,k in itertools.product(histories,protocol['capability_scopes'],protocol['loss_bounds']):
            graph=Graph.read(original/'captures'/history/'manifest.json');caps=caps_for(graph,scope)
            case=f'{history}-{scope}-k{k}'
            for name,solver in [('RecoverML_exact',exact),('scenario_exact',reference)]:
                clock=time.perf_counter()
                try:
                    selected,status,diag=solver(graph,caps,k,time_limit_s=protocol['solver_time_limit_s'])
                    record=dict(case=case,policy=name,status=status,diagnostic=diag,selected=sorted(selected),
                        actual_bytes=retained_bytes(graph,selected,caps,k),recertification_wall_s=time.perf_counter()-clock,
                        record_origin='Post-interruption metadata-only recertification; not original timed planning or original selected identities',
                        recertification_environment=environment(),source_manifest_sha256=digest((original/'captures'/history/'manifest.json').read_bytes()))
                    plans.append(record)
                except Exception as exc:
                    failures.append(dict(case=case,policy=name,phase='metadata_recertification',error=repr(exc)))
                    plans.append(dict(case=case,policy=name,status='exception',diagnostic={},selected=[],actual_bytes=None,
                        record_origin='Post-interruption metadata-only recertification failure'))
            dump(destination/'planner_recertification_checkpoint.json',plans)
    new_rows=0;new_raw=0
    expected_cases={f'digits_forest-{seed}-{scope}-k{k}' for seed,scope,k in itertools.product(
        resume['rerun_seeds'],protocol['capability_scopes'],protocol['loss_bounds'])}
    inventory=json.loads((resumed/'case_inventory.json').read_text())
    if {c['case'] for c in inventory}!=expected_cases:raise RuntimeError('Missing declared case inventory')
    for item in inventory:
        source=resumed/'cases'/item['case'];report=json.loads((source/'report.json').read_text())
        if report['source_changed_during_run']:raise RuntimeError('Source changed during worker')
        rs=list(csv.DictReader((source/'summary.csv').open()));ts,error=readable_records(source/'execution_traces.jsonl.gz')
        if error:raise RuntimeError('Rerun compressed trace incomplete: '+item['case'])
        if len(rs)!=40 or len(ts)!=report['requests']:raise RuntimeError('Incomplete rerun case '+item['case'])
        rows+=rs;traces+=ts;new_rows+=len(rs);new_raw+=len(ts)
        for p in json.loads(gzip.decompress((source/'planner_records.json.gz').read_bytes())):
            p['record_origin']='Fresh rerun timed planning';plans.append(p)
        sensitivity+=json.loads(gzip.decompress((source/'sensitivity.json.gz').read_bytes()))
        failures+=report['failures'];case_receipts.append(dict(case=item['case'],report=report,
            summary_sha256=digest((source/'summary.csv').read_bytes()),trace_sha256=digest((source/'execution_traces.jsonl.gz').read_bytes()),
            run_start_sha256=digest((source/'run_start.json').read_bytes())))
    captures+=json.loads((resumed/'fresh_capture_inventory.json').read_text())
    if new_rows!=resume['expected_new_rows'] or new_raw!=resume['expected_new_requests']:
        raise RuntimeError('Fresh rerun denominator differs from declared protocol')
    if len(rows)!=resume['expected_final_rows'] or len(traces)!=resume['expected_final_requests']:
        raise RuntimeError('Final denominator differs from declared protocol')
    identities=[request_identity(t) for t in traces]
    if len(identities)!=len(set(identities)):raise RuntimeError('Duplicate final request')
    with (destination/'summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    with gzip.open(destination/'execution_traces.jsonl.gz','wt') as stream:
        for record in traces:stream.write(json.dumps(record,allow_nan=False)+'\n')
    for name,values in [('planner_records',plans),('sensitivity',sensitivity)]:
        with gzip.open(destination/(name+'.json.gz'),'wt') as stream:json.dump(values,stream,allow_nan=False)
    dump(destination/'capture_inventory.json',captures)
    if (resumed/'captures.tar.gz').exists():
        receipt=json.loads((resumed/'capture_archive_receipt.json').read_text())
        if digest((resumed/'captures.tar.gz').read_bytes())!=receipt['sha256']:
            raise RuntimeError('Frozen capture archive changed')
        shutil.copyfile(resumed/'captures.tar.gz',destination/'captures.tar.gz')
    else:
        with tarfile.open(destination/'captures.tar.gz','w:gz') as archive:
            for history in histories:archive.add(original/'captures'/history,arcname='captures/'+history)
            for info in captures:
                if info['history'] not in histories:archive.add(resumed/'captures'/info['history'],arcname='captures/'+info['history'])
    # Preserve exact old and rerun source versions in one compact indexed archive.
    source_items=[('original',original/'source_snapshot'),('fresh_prepare',resumed/'source_snapshot')]
    source_items += [(item['case'],resumed/'cases'/item['case']/'source_snapshot') for item in inventory]
    index=[]
    with tarfile.open(destination/'source_versions.tar.gz','w:gz') as archive:
        for label,path in source_items:
            for file in sorted(path.glob('*.py')):
                archive.add(file,arcname=label+'/'+file.name)
                index.append(dict(version=label,path=file.name,sha256=digest(file.read_bytes())))
    dump(destination/'source_versions.json',index)
    raw_path=destination/'execution_traces.jsonl.gz'
    report=dict(histories=len(captures),case_policy_budget_rows=len(rows),requests=len(traces),
        exact=sum(int(r['exact']) for r in rows),expected_blocked=sum(int(r['blocked']) for r in rows),
        unexpected=sum(int(r['unexpected']) for r in rows),failures=failures,source_changed_during_run=[],
        sensitivity_rows=len(sensitivity),finish_timestamp_ns=time.time_ns(),raw_trace_sha256=digest(raw_path.read_bytes()),
        limitations=['Eight constructed captures are not a random production sample','Repeated requests are correlated',
            'Original nonforest measurements and fresh forest measurements were not concurrent with each other',
            resume['concurrency_qualification'],'Exact minima do not maximize partial coverage below their feasibility budget',
            'One trial per request and process high-water RSS and cached Linux I/O are descriptive',
            'Lost original planner certificates were recomputed as labelled metadata only; original planning times remain in original summary',
            'Uniform-cost annotation sensitivity here is not the separate nonuniform published-component sensitivity study',
            'No GPU, energy or second-machine result is claimed'])
    dump(destination/'report.json',report)
    receipt=dict(start_timestamp_ns=start,finish_timestamp_ns=time.time_ns(),original_summary_rows=len(original_rows),
        original_readable_requests=len(original_raw),original_gzip_error=truncation,reused_histories=selection,
        reused_rows=len(rows)-new_rows,reused_requests=len(traces)-new_raw,new_rows=new_rows,new_requests=new_raw,
        excluded_partial_forest_rows=sum(r['history'].startswith('digits_forest') for r in original_rows),
        excluded_partial_forest_raw=sum(r['history'].startswith('digits_forest') for r in original_raw),
        exclusion='All forest conditions rerun, as frozen before new measurements; no performance or outcome selection',
        worker_receipts=case_receipts,source_versions_sha256=digest((destination/'source_versions.tar.gz').read_bytes()),
        capture_archive_sha256=digest((destination/'captures.tar.gz').read_bytes()),
        original_files_still_match_frozen_hashes=all(digest((original/name).read_bytes())==resume[key]
            for key,name in [('original_summary_sha256','summary.csv'),('original_trace_sha256','execution_traces.jsonl.gz')]))
    dump(destination/'merge_receipt.json',receipt)
    if not receipt['original_files_still_match_frozen_hashes']:raise RuntimeError('Original files mutated')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',type=Path,default=ROOT/'results/research/scientific_audit_oct15')
    p.add_argument('--resumed',type=Path,default=ROOT/'results/research/scientific_resume_oct15')
    p.add_argument('--output',type=Path,default=ROOT/'results/research/scientific_complete_oct15')
    a=p.parse_args();print(json.dumps(merge(a.original,a.resumed,a.output),indent=2))
