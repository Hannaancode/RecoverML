#!/usr/bin/env python3
"""Counterfactual ledger controls on temporary copies of a closed GB study.

These controls test the independent analyzer and do not rerun model fitting or
modify the original execution evidence. They do not replace payload validation.
"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile
import tarfile


INPUTS = (
    'protocol.json', 'capture_inventory.json', 'report.json',
    'planner_records.json', 'blob_inventory.json', 'runtime_store_index.json',
    'manifest.json', 'summary.csv', 'allowed_scenario_certificates.json',
    'execution_traces.jsonl.gz', 'native_dvc_report.json',
    'native_dvc_commands.json',
    'store_membership.json', 'selected_frontier.tar.gz',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cross_links(study):
    """Reconcile displayed numeric summaries with the recorded plan/raw inputs."""
    load = lambda name: json.loads((study / name).read_text())
    plans = {(row['scope'], row['policy']): row for row in load('planner_records.json')}
    stores = load('runtime_store_index.json')
    with (study / 'summary.csv').open() as stream:
        summaries = list(csv.DictReader(stream))
    with gzip.open(study / 'execution_traces.jsonl.gz', 'rt') as stream:
        traces = [json.loads(line) for line in stream]
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    def close(a, b):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)
    def quantile(values, probability):
        values = sorted(values)
        index = (len(values) - 1) * probability
        low = int(index)
        high = min(low + 1, len(values) - 1)
        return values[low] + (values[high] - values[low]) * (index - low)
    for row in summaries:
        identity = row['scope'] + '/' + row['policy']
        plan = plans[(row['scope'], row['policy'])]
        store = stores[row['runtime_key']]
        check(row['selected_sha256'] == plan['selected_sha256'] == store['selected_sha256'], identity + ' selected identity')
        check(plan['selected'] == store['selected'], identity + ' selected physical set')
        for field, plan_field in [('retained_bytes', 'retained_bytes'), ('gzip_retained_bytes', 'compressed_retained_bytes'),
                                  ('baseline_bytes', 'budget_bytes'), ('allowed_requests', 'allowed_structural_requests'),
                                  ('allowed_exact', 'allowed_structural_exact')]:
            check(int(row[field]) == plan[plan_field], identity + ' ' + field)
        check(int(row['saving_bytes']) == plan['budget_bytes'] - plan['retained_bytes'], identity + ' saved bytes')
        check(close(row['planning_s'], plan['planning_s']), identity + ' planning time')
        for field, store_field in [('stress_requests', 'actual_requests'), ('stress_exact', 'exact'),
                                   ('stress_expected_blocked', 'expected_blocked'), ('stress_unexpected', 'unexpected')]:
            check(int(row[field]) == store[store_field], identity + ' ' + field)
        for suffix in ('mean', 'p50', 'p90', 'p99'):
            check(close(row['stress_latency_' + suffix + '_s'], store['elapsed_' + suffix + '_s']), identity + ' latency ' + suffix)
    for key, store in stores.items():
        rows = [row for row in traces if row['runtime_key'] == key]
        elapsed = [row['elapsed_s'] for row in rows]
        check(close(store['elapsed_mean_s'], sum(elapsed) / len(elapsed)), key + ' mean')
        check(close(store['cpu_total_s'], sum(row['cpu_s'] for row in rows)), key + ' CPU total')
        for label, probability in [('p50', .5), ('p90', .9), ('p99', .99)]:
            check(close(store['elapsed_' + label + '_s'], quantile(elapsed, probability)), key + ' ' + label)
        for row in rows:
            check(row['selected_sha256'] == store['selected_sha256'] and row['disabled'] == store['disabled'], key + '/' + row['version'] + ' raw store identity')
    return dict(status='PASS' if not errors else 'FAIL', errors=errors,
                summary_rows=len(summaries), runtime_stores=len(stores), raw_requests=len(traces))


def frontier_archive(study, module):
    load = lambda name: json.loads((study / name).read_text())
    receipt = load('store_membership.json')
    inventory = load('blob_inventory.json')
    plans = load('planner_records.json')
    exact = next(row for row in plans if row['scope'] == 'preprocessing' and row['policy'] == 'RecoverML_exact')
    archive = study / 'selected_frontier.tar.gz'
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    check(sha(archive) == receipt['frontier_archive_sha256'], 'Archive hash differs from membership receipt')
    check(exact['selected'] == receipt['frontier_selected'], 'Archived frontier differs from exact preprocessing selection')
    expected_plans = [dict(scope=row['scope'], policy=row['policy'], selected=row['selected'], selected_sha256=row['selected_sha256']) for row in plans]
    check(receipt['plans'] == expected_plans, 'Membership plan list differs from planner ledger')
    members = []
    payload_bytes = 0
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getnames()
        expected_members = {'manifest.json', 'capability_contract.json'} | {'blobs/' + blob + '.pkl' for blob in exact['selected']}
        check(set(members) == expected_members and len(members) == len(expected_members), 'Missing extra or duplicate archive members')
        manifest = json.loads(source.extractfile('manifest.json').read())
        check(manifest == load('manifest.json'), 'Archived manifest differs from study manifest')
        check(source.extractfile('capability_contract.json').read() == module.contract(exact['capabilities'], 1), 'Archived capability contract differs')
        for blob in exact['selected']:
            data = source.extractfile('blobs/' + blob + '.pkl').read()
            check(hashlib.sha256(data).hexdigest() == blob, 'Archived payload hash differs: ' + blob)
            check(len(data) == inventory[blob]['bytes'], 'Archived payload size differs: ' + blob)
            payload_bytes += len(data)
    check(payload_bytes == receipt['frontier_payload_bytes'], 'Frontier payload accounting differs')
    return dict(status='PASS' if not errors else 'FAIL', errors=errors, archive_sha256=sha(archive),
                payload_files=len(exact['selected']), payload_bytes=payload_bytes, archive_members=members)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    analyzer = Path(__file__).with_name('analyze_gigabyte_history.py')
    spec = importlib.util.spec_from_file_location('gigabyte_analyzer', analyzer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Plots and prose do not contribute to semantic reconciliation and are
    # omitted only in these disposable controls. analyze() is unchanged.
    module.write_results = lambda *unused: None
    before = {name: sha(args.study / name) for name in INPUTS}
    linked = cross_links(args.study)
    (args.output / 'numeric_cross_links.json').write_text(json.dumps(linked, indent=2) + '\n')
    archived = frontier_archive(args.study, module)
    (args.output / 'frontier_archive.json').write_text(json.dumps(archived, indent=2) + '\n')
    cases = [
        ('unchanged', True),
        ('structural_reordered', True),
        ('structural_duplicate_identity', False),
        ('structural_flipped_recoverability', False),
        ('structural_missing_record', False),
        ('runtime_duplicate_identity', False),
    ]
    receipts = []
    with tempfile.TemporaryDirectory(prefix='recoverml_ledger_controls_') as root:
        for name, should_pass in cases:
            folder = Path(root) / name
            folder.mkdir()
            for item in INPUTS:
                shutil.copy2(args.study / item, folder / item)
            structural_path = folder / 'allowed_scenario_certificates.json'
            records = json.loads(structural_path.read_text())
            mutation = None
            if name == 'structural_reordered':
                records.reverse()
                mutation = 'Reverse complete ledger order without changing records'
            elif name == 'structural_duplicate_identity':
                records[1] = dict(records[0])
                mutation = 'Replace second record with first while preserving row count'
            elif name == 'structural_flipped_recoverability':
                records[0]['recoverable'] = not records[0]['recoverable']
                mutation = 'Invert one recoverability outcome'
            elif name == 'structural_missing_record':
                records.pop()
                mutation = 'Remove one complete structural record'
            if name.startswith('structural_'):
                structural_path.write_text(json.dumps(records, indent=2) + '\n')
            if name == 'runtime_duplicate_identity':
                trace_path = folder / 'execution_traces.jsonl.gz'
                with gzip.open(trace_path, 'rt') as stream:
                    rows = [json.loads(line) for line in stream]
                rows[1] = dict(rows[0])
                with gzip.open(trace_path, 'wt') as stream:
                    for row in rows:
                        stream.write(json.dumps(row) + '\n')
                mutation = 'Replace second actual runtime request with first at fixed row count'
            answer = module.analyze(folder)
            changed = [item for item in INPUTS if sha(folder / item) != before[item]]
            record = dict(
                case=name, mutation=mutation, expected_status='PASS' if should_pass else 'FAIL',
                observed_status=answer['status'], errors=answer['errors'],
                changed_inputs=changed,
                control_passed=(answer['status'] == ('PASS' if should_pass else 'FAIL')),
            )
            receipts.append(record)
            (args.output / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    after = {name: sha(args.study / name) for name in INPUTS}
    result = dict(
        status='PASS' if before == after and linked['status'] == archived['status'] == 'PASS' and all(row['control_passed'] for row in receipts) else 'FAIL',
        controls=len(receipts), controls_passed=sum(row['control_passed'] for row in receipts),
        original_inputs_unchanged=before == after, original_input_sha256=before,
        analyzer_sha256=sha(analyzer), cases=receipts,
        numeric_cross_links=linked,
        frontier_archive=archived,
        scope='Ledger semantic controls only; training and disk recovery are not rerun and payload verification is separate',
    )
    (args.output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'controls', 'controls_passed', 'original_inputs_unchanged')}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
