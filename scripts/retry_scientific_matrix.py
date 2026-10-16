"""Apply the frozen, outcome-independent case retry rule and reconcile the matrix.

All open measurement streams belong under a unique /tmp directory.  The previous
attempts are never edited.  This wrapper changes neither captures nor operators.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import gzip
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from recoverml.core import Graph, digest, environment
from recoverml.scientific_workflows import caps_for
from recoverml.robust_heuristics import fault_sets
from recoverml.scientific_benchmarks import dump, run
from resume_scientific_matrix import readable_records, request_identity


def audit_case(source, protocol, captures, case):
    """Check the exact declared identities, counters and measured aggregates."""
    rows = list(csv.DictReader((source / 'summary.csv').open()))
    traces, error = readable_records(source / 'execution_traces.jsonl.gz')
    report = json.loads((source / 'report.json').read_text())
    workflow = protocol['workflows'][0]
    seed = protocol['seeds'][0]
    history = f'{workflow}-{seed}'
    graph = Graph.read(captures / history / 'manifest.json')
    scope, k = protocol['capability_scopes'][0], protocol['loss_bounds'][0]
    expected = {(case, method, float(budget), str(version), tuple(lost))
        for method, budget in itertools.product(protocol['methods'],
            protocol['optional_snapshot_budget_fractions'])
        for lost in fault_sets(caps_for(graph, scope), k) for version in graph.targets}
    expected_rows = {(case, method, float(budget))
        for method, budget in itertools.product(protocol['methods'],
            protocol['optional_snapshot_budget_fractions'])}
    actual = [request_identity(t) for t in traces]
    row_ids = [(r['case'], r['policy'], float(r['budget_fraction'])) for r in rows]
    errors = []
    if error: errors.append('gzip integrity: ' + error)
    if len(actual) != len(set(actual)) or set(actual) != expected:
        errors.append('Incomplete or duplicated manifest-derived raw identity grid')
    if len(row_ids) != len(set(row_ids)) or set(row_ids) != expected_rows:
        errors.append('Incomplete or duplicated summary grid')
    groups = defaultdict(list)
    for trace in traces:
        groups[request_identity(trace)[:3]].append(trace)
        if not trace['capture_archive_absent']:
            errors.append('Archive was visible during replay')
        if trace['end_timestamp_ns'] < trace['start_timestamp_ns'] or trace['latency_s'] < 0:
            errors.append('Invalid raw timestamp or latency')
    # Match NumPy's default linear quantile without creating a new dependency.
    def quantile(values, fraction):
        values = sorted(values); pos = (len(values) - 1) * fraction
        lo = int(pos); hi = min(lo + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)
    for row in rows:
        key = (row['case'], row['policy'], float(row['budget_fraction']))
        raw = groups[key]
        counts = dict(requests=len(raw), exact=sum(int(t['exact']) for t in raw),
            blocked=sum(int(t['expected_blocked']) for t in raw),
            unexpected=sum(int(t['unexpected']) for t in raw))
        if any(int(row[name]) != value for name, value in counts.items()):
            errors.append('Summary/raw counters: ' + str(key))
        if raw:
            latency = [t['latency_s'] for t in raw]
            metrics = dict(latency_mean_s=sum(latency) / len(latency),
                latency_p50_s=quantile(latency, .5), latency_p90_s=quantile(latency, .9),
                latency_p99_s=quantile(latency, .99), cpu_total_s=sum(t['cpu_s'] for t in raw),
                read_bytes=sum(t['io_delta'].get('read_bytes', 0) for t in raw),
                write_bytes=sum(t['io_delta'].get('write_bytes', 0) for t in raw),
                operation_events=sum(len(t['events']) for t in raw))
            for name, value in metrics.items():
                if not math.isclose(float(row[name]), value, rel_tol=1e-12, abs_tol=1e-12):
                    errors.append('Summary/raw measured metric: ' + str(key) + ' ' + name)
    if report['requests'] != len(traces): errors.append('Report/raw request count')
    if report['raw_trace_sha256'] != digest((source / 'execution_traces.jsonl.gz').read_bytes()):
        errors.append('Report raw trace hash')
    for name, field in [('exact', 'exact'), ('expected_blocked', 'blocked'), ('unexpected', 'unexpected')]:
        if report[name] != sum(int(r[field]) for r in rows):
            errors.append('Report/summary counter ' + name)
    drift = report['source_changed_during_run']
    return dict(case=case, rows=len(rows), requests=len(traces),
        expected_requests=len(expected), integrity_errors=sorted(set(errors)),
        source_changed_during_run=drift, accepted=not errors and not drift,
        summary_sha256=digest((source / 'summary.csv').read_bytes()),
        trace_sha256=digest((source / 'execution_traces.jsonl.gz').read_bytes()),
        report_sha256=digest((source / 'report.json').read_bytes()))


def prepare(destination, protocol_path):
    destination = destination.resolve()
    if not destination.is_relative_to(Path('/tmp')):
        raise ValueError('Use a new /tmp directory for long-lived measurement streams')
    retry = json.loads(protocol_path.read_text())
    original = ROOT / retry['original_attempt']
    if digest((original / 'captures.tar.gz').read_bytes()) != retry['frozen_capture_archive_sha256']:
        raise RuntimeError('Frozen capture archive changed')
    items = json.loads((original / 'case_inventory.json').read_text())
    diagnostics = []
    for item in items:
        case_protocol_path = ROOT / item['protocol']
        if digest(case_protocol_path.read_bytes()) != item['protocol_sha256']:
            raise RuntimeError('Original case protocol changed')
        case_protocol = json.loads(case_protocol_path.read_text())
        diagnostics.append(audit_case(original / 'cases' / item['case'], case_protocol,
            original / 'captures', item['case']))
    selected = sorted(d['case'] for d in diagnostics if not d['accepted'])
    reused = sorted(d['case'] for d in diagnostics if d['accepted'])
    if selected != sorted(retry['selected_cases']) or reused != sorted(retry['reused_cases']):
        raise RuntimeError('Frozen case selection no longer matches the declared audit rule')
    destination.mkdir(parents=True, exist_ok=False)
    for name in ['protocol.json', 'resume_protocol.json', 'fresh_capture_inventory.json',
                 'capture_archive_receipt.json', 'captures.tar.gz']:
        shutil.copyfile(original / name, destination / name)
    dump(destination / 'retry_protocol.json', retry)
    dump(destination / 'previous_case_audit.json', diagnostics)
    # Source archive has all original and fresh manifests, including nonforest
    # stores.  No new models are captured and no environment guard is changed.
    with tarfile.open(destination / 'captures.tar.gz', 'r:gz') as archive:
        archive.extractall(destination, filter='data')
    (destination / 'case_protocols').mkdir()
    (destination / 'cases').mkdir()
    fresh_items = []
    for item in items:
        target = destination / 'case_protocols' / (item['case'] + '.json')
        shutil.copyfile(ROOT / item['protocol'], target)
        fresh_items.append(dict(case=item['case'], protocol=str(target),
            protocol_sha256=digest(target.read_bytes())))
        if item['case'] in reused:
            (destination / 'cases' / item['case']).symlink_to((original / 'cases' / item['case']).resolve(), target_is_directory=True)
    dump(destination / 'case_inventory.json', fresh_items)
    (destination / 'source_snapshot').mkdir()
    hashes = {}
    for path in sorted((ROOT / 'src/recoverml').glob('*.py')):
        shutil.copyfile(path, destination / 'source_snapshot' / path.name)
        hashes[path.name] = digest(path.read_bytes())
    dump(destination / 'retry_start.json', dict(timestamp_ns=time.time_ns(), environment=environment(),
        source_sha256=hashes, retry_protocol_sha256=digest(protocol_path.read_bytes()),
        git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        original_attempt=str(original), selected_cases=selected, reused_cases=reused,
        wrapper_sha256=digest(Path(__file__).read_bytes())))
    return dict(output=str(destination), retry_cases=len(selected), reused_cases=len(reused))


def run_case(destination, case, cache):
    start = json.loads((destination / 'retry_start.json').read_text())
    if case not in start['selected_cases']:
        raise ValueError('Cannot rerun an undeclared case')
    if any(digest((ROOT / 'src/recoverml' / name).read_bytes()) != value
           for name, value in start['source_sha256'].items()):
        raise RuntimeError('Source changed since retry preparation')
    item = next(i for i in json.loads((destination / 'case_inventory.json').read_text()) if i['case'] == case)
    path = Path(item['protocol'])
    if digest(path.read_bytes()) != item['protocol_sha256']:
        raise RuntimeError('Frozen derived protocol changed')
    return run(destination / 'cases' / case, path, cache, capture_input=destination / 'captures')


def run_cases(destination, cache):
    retry = json.loads((destination / 'retry_protocol.json').read_text())
    logs = destination / 'worker_logs'; logs.mkdir(exist_ok=False)
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONPATH=str(ROOT / 'src'))
    receipts = []
    def worker(case):
        command = [sys.executable, str(Path(__file__).resolve()), '--output', str(destination),
            '--case', case, '--hyppo-cache', str(cache)]
        started = time.time_ns()
        with (logs / (case + '.txt')).open('w') as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        receipt = dict(case=case, command=command, start_timestamp_ns=started,
            end_timestamp_ns=time.time_ns(), exit_code=result.returncode)
        dump(logs / (case + '.json'), receipt)
        return receipt
    with ThreadPoolExecutor(max_workers=retry['case_workers']) as pool:
        for job in as_completed([pool.submit(worker, case) for case in retry['selected_cases']]):
            receipt = job.result(); receipts.append(receipt)
            dump(destination / 'retry_worker_execution.json', receipts)
            print(json.dumps(receipt), flush=True)
    if any(r['exit_code'] for r in receipts): raise RuntimeError('A declared retry worker failed')
    return dict(completed_cases=len(receipts))


def merge(destination, output):
    from merge_scientific_resume import merge as merge_matrix
    retry = json.loads((destination / 'retry_protocol.json').read_text())
    items = json.loads((destination / 'case_inventory.json').read_text())
    audits = [audit_case(destination / 'cases' / item['case'], json.loads(Path(item['protocol']).read_text()),
        destination / 'captures', item['case']) for item in items]
    dump(destination / 'accepted_case_audit.json', audits)
    if any(not a['accepted'] for a in audits): raise RuntimeError('A final case failed strict reconciliation or source guard')
    if sum(a['rows'] for a in audits) != retry['expected_final_forest_rows']:
        raise RuntimeError('Final forest row denominator')
    if sum(a['requests'] for a in audits) != retry['expected_final_forest_requests']:
        raise RuntimeError('Final forest raw denominator')
    resume = json.loads((destination / 'resume_protocol.json').read_text())
    report = merge_matrix(ROOT / resume['original_directory'], destination, output)
    for name in ['retry_protocol.json', 'retry_start.json', 'previous_case_audit.json',
                 'accepted_case_audit.json', 'retry_worker_execution.json']:
        shutil.copyfile(destination / name, output / name)
    shutil.copytree(destination / 'worker_logs', output / 'retry_worker_logs')
    # Keep the incomplete original and every flagged previous case available.
    previous = ROOT / retry['original_attempt']
    original = ROOT / resume['original_directory']
    with tarfile.open(output / 'superseded_attempts.tar.gz', 'w:gz') as archive:
        for name in ['summary.csv', 'execution_traces.jsonl.gz', 'run_start.json', 'protocol.json']:
            if (original / name).exists(): archive.add(original / name, arcname='original/' + name)
        archive.add(original / 'source_snapshot', arcname='original/source_snapshot')
        for path in sorted(previous.glob('*.json')):
            archive.add(path, arcname='first_forest_attempt/' + path.name)
        for path in sorted((previous / 'cases').iterdir()):
            archive.add(path, arcname='first_forest_attempt/cases/' + path.name)
    receipt = dict(timestamp_ns=time.time_ns(), accepted_cases=audits,
        previous_cases=json.loads((destination / 'previous_case_audit.json').read_text()),
        selection_rule=retry['decision_rule'], original_failed_attempts_preserved=True,
        superseded_archive_sha256=digest((output / 'superseded_attempts.tar.gz').read_bytes()),
        reused_case_count=len(retry['reused_cases']), retry_case_count=len(retry['selected_cases']),
        qualification='Original six complete nonforest histories lack a closed end-of-run source guard because that process was interrupted; their source snapshot and strict per-request environment/operator guards and raw reconciliation remain available')
    dump(output / 'retry_merge_receipt.json', receipt)
    report['source_guard_scope'] = receipt['qualification']
    dump(output / 'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=ROOT / 'configs/scientific_retry_oct15.json')
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run-cases', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--merge-to', type=Path)
    parser.add_argument('--hyppo-cache', type=Path, default=ROOT.parent / 'baseline_sources/HYPPO/Components')
    args = parser.parse_args(); destination = args.output.resolve()
    if args.prepare: result = prepare(destination, args.protocol.resolve())
    elif args.run_cases: result = run_cases(destination, args.hyppo_cache.resolve())
    elif args.case: result = run_case(destination, args.case, args.hyppo_cache.resolve())
    elif args.merge_to: result = merge(destination, args.merge_to.resolve())
    else: parser.error('Specify --prepare, --run-cases, --case or --merge-to')
    print(json.dumps(result, indent=2))
