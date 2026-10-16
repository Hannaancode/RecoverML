#!/usr/bin/env python3
"""Reconcile whole retinal captures before joining an interrupted fixed grid.

No request timings are reconstructed. A capture is reusable only when every
declared row, raw request, store, planner entry and native receipt is present.
"""
import argparse
from collections import Counter, defaultdict
import copy
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import tarfile

import numpy as np

from recoverml.capability_retention import retained_bytes, restricted
from recoverml.core import Graph
from recoverml.eyeai_workflow import capabilities_for, target_view
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(directory, stem):
    path = directory / (stem + '.json')
    if path.exists():
        return json.loads(path.read_text())
    with (directory / (stem + '.jsonl')).open() as handle:
        return [json.loads(line) for line in handle]


def source(directory, estimator):
    with (directory / 'summary.csv').open() as handle:
        all_rows = list(csv.DictReader(handle))
    rows = [row for row in all_rows if row['estimator'] == estimator]
    ids = {row['condition_id'] for row in rows}
    path = directory / 'raw.jsonl.gz'
    opener = gzip.open if path.exists() else open
    if not path.exists():
        path = directory / 'raw.jsonl'
    all_raw, raw = 0, []
    with opener(path, 'rt') as handle:
        for line in handle:
            record = json.loads(line)
            all_raw += 1
            if record['estimator'] == estimator:
                raw.append(record)
    plans = [row for row in read_json(directory, 'planner_records') if row['condition_id'] in ids]
    stores = [row for row in read_json(directory, 'store_index' if (directory / 'store_index.json').exists() else 'store_records') if row['condition_id'] in ids]
    captures = {row['capture_id'] for row in rows}
    all_commands = read_json(directory, 'native_commands')
    commands = [row for row in all_commands if any(
        Path(row['cwd']).name.startswith(capture + '_') for capture in captures)]
    return dict(directory=directory, rows=rows, raw=raw, plans=plans, stores=stores,
                commands=commands, captures=captures, original_rows=len(all_rows), original_raw=all_raw,
                original_native_commands=len(all_commands), original_native_checkouts=sum(
                    row['command'][1:4] == ['-m', 'dvc', 'checkout'] for row in all_commands))


def keyed(values):
    result = {row['condition_id']: row for row in values}
    if len(result) != len(values):
        raise RuntimeError('Duplicate condition ledger entry')
    return result


def audit(data, protocol, estimator):
    rows = keyed(data['rows'])
    plans, stores = keyed(data['plans']), keyed(data['stores'])
    expected = {f'{estimator}_s{seed}_v{versions}__{target}__{availability}__{policy}'
                for seed, versions, target, availability, policy in itertools.product(
                    protocol['seeds'], protocol['versions'], protocol['targets'],
                    protocol['availability'], protocol['policies'])}
    if set(rows) != expected or set(plans) != expected or set(stores) != expected:
        raise RuntimeError('Incomplete whole-capture summary/planner/store grid: ' + estimator)
    by_condition = defaultdict(list)
    for raw in data['raw']:
        by_condition[raw['condition_id']].append(raw)
    if set(by_condition) != expected:
        raise RuntimeError('Incomplete raw condition set')
    command_by_id = {record['id']: record for record in data['commands']}
    if len(command_by_id) != len(data['commands']) or any(row['returncode'] for row in data['commands']):
        raise RuntimeError('Invalid native command identities or failed native commands')
    checkout_ids = set()
    blobs_verified = set()
    for condition in sorted(expected):
        row, plan, store = rows[condition], plans[condition], stores[condition]
        original = Graph.read(data['directory'] / 'captures' / row['capture_id'] / 'manifest.json')
        graph = target_view(original, row['target_mode'])
        caps, k = capabilities_for(graph, row['availability'])
        if store['manifest'] != graph.manifest() or store['capabilities'] != caps or store['k'] != k:
            raise RuntimeError('Store manifest or availability contract differs: ' + condition)
        selected = set(store['selected'])
        if sorted(selected) != plan['selected'] or len(selected) != len(store['selected']):
            raise RuntimeError('Planner/store memberships differ: ' + condition)
        if any(not math.isclose(float(row[field]), float(plan[field]), rel_tol=1e-10, abs_tol=1e-12)
               for field in ('planning_s', 'planning_cpu_s')):
            raise RuntimeError('Planner/summary timing differs: ' + condition)
        if retained_bytes(graph, selected, caps, k) != int(row['retained_bytes']):
            raise RuntimeError('Store byte accounting differs: ' + condition)
        for blob in selected - blobs_verified:
            if sha(data['directory'] / 'payload_blobs' / (blob + '.pkl')) != blob:
                raise RuntimeError('Retained payload does not match its SHA-256 identity')
        blobs_verified.update(selected)
        expected_requests = {(tuple(fault), version) for fault in fault_sets(caps, k) for version in graph.targets}
        records = by_condition[condition]
        actual_requests = [(tuple(record['fault']), record['version']) for record in records]
        if len(actual_requests) != len(set(actual_requests)) or set(actual_requests) != expected_requests:
            raise RuntimeError('Incomplete or duplicated fault/version request grid: ' + condition)
        for fault in fault_sets(caps, k):
            if not certificate(restricted(graph, caps, fault), selected)['complete']:
                raise RuntimeError('Store fails independent structural closure: ' + condition)
        if len(records) != int(row['requests']) or sum(bool(r['exact']) for r in records) != int(row['exact']) or sum(r['error'] is not None for r in records) != int(row['errors']):
            raise RuntimeError('Raw/summary counts differ: ' + condition)
        for record in records:
            expected_hashes = [graph.nodes[node].blob for node in graph.targets[record['version']]]
            if record['expected_sha256'] != expected_hashes or (record['exact'] and record['actual_sha256'] != expected_hashes):
                raise RuntimeError('Raw target hashes differ: ' + condition)
            if record['policy'].startswith('DVC_'):
                receipt = record['native_checkout_receipt']
                native = command_by_id[receipt['command_receipt_id']]
                if native['command'][1:4] != ['-m', 'dvc', 'checkout']:
                    raise RuntimeError('Native checkout receipt points at another command')
                if receipt != plan['diagnostics']['native_checkout_receipts'][record['version']]:
                    raise RuntimeError('Native raw and planner receipt differ')
                nodes = set(graph.targets[record['version']])
                if record['policy'] == 'DVC_all_stages':
                    pending = list(nodes)
                    while pending:
                        for dependency in graph.nodes[pending.pop()].deps:
                            if dependency not in nodes:
                                nodes.add(dependency)
                                pending.append(dependency)
                verified = {graph.nodes[node].blob for node in nodes}
                if sorted(verified) != receipt['verified_blobs']:
                    raise RuntimeError('Native checkout verified set differs from declared policy')
                if not math.isclose(receipt['native_checkout_s'], native['elapsed_s'], rel_tol=1e-10):
                    raise RuntimeError('Native checkout timing differs from actual command receipt')
                if native['command'][-1] != 'payload/' + record['version'] + '.dvc':
                    raise RuntimeError('Native checkout receipt points at another version')
                checkout_ids.add(native['id'])
        latencies = [record['elapsed_s'] for record in records]
        metrics = {'mean_restore_s': np.mean(latencies), 'p50_s': np.quantile(latencies, .5),
                   'p90_s': np.quantile(latencies, .9), 'p99_s': np.quantile(latencies, .99),
                   'recovery_cpu_s': sum(record['process_cpu_s'] for record in records)}
        if any(not math.isclose(float(row[field]), float(value), rel_tol=1e-10, abs_tol=1e-12) for field, value in metrics.items()):
            raise RuntimeError('Raw latency or CPU metrics differ: ' + condition)
    native_ids = {record['id'] for record in data['commands'] if record['command'][1:4] == ['-m', 'dvc', 'checkout']}
    if checkout_ids != native_ids:
        raise RuntimeError('Unused or missing native checkout receipt in retained capture')
    expected_checkouts = sum(protocol['versions']) * len(protocol['seeds']) * len(protocol['targets']) * 2
    if len(checkout_ids) != expected_checkouts:
        raise RuntimeError('Native checkout count differs from capture grid')
    return dict(status='PASS', estimator=estimator, complete_captures=len(data['captures']),
                summary_rows=len(rows), raw_requests=len(data['raw']), native_checkout_commands=len(native_ids),
                unique_verified_payload_blobs=len(blobs_verified), source_rows_excluded=data['original_rows'] - len(rows),
                source_raw_requests_excluded=data['original_raw'] - len(data['raw']),
                source_native_commands_excluded=data['original_native_commands'] - len(data['commands']),
                source_native_checkout_commands_excluded=data['original_native_checkouts'] - len(native_ids))


def merge(original, rerun, output, protocol_file, audit_only=False):
    original, output = Path(original), Path(output)
    protocol = json.loads(Path(protocol_file).read_text())
    old = source(original, 'logistic')
    receipts = [audit(old, protocol, 'logistic')]
    if audit_only:
        print(json.dumps(receipts[0], indent=2))
        return receipts
    new = source(Path(rerun), 'forest')
    receipts.append(audit(new, protocol, 'forest'))
    old_hashes = json.loads((original / 'source_hashes.json').read_text())
    new_hashes = json.loads((Path(rerun) / 'source_hashes.json').read_text())
    if old_hashes != new_hashes:
        raise RuntimeError('Rerun source/config snapshots differ from interrupted study')
    if output.exists():
        raise RuntimeError('Refuse to overwrite a merged study')
    output.mkdir(parents=True)
    shutil.copytree(Path(rerun) / 'source_snapshot', output / 'source_snapshot')
    shutil.copy2(Path(rerun) / 'source_hashes.json', output / 'source_hashes.json')
    shutil.copy2(protocol_file, output / 'protocol.json')
    if (original / 'data_acquisition.json').exists():
        shutil.copy2(original / 'data_acquisition.json', output / 'data_acquisition.json')
    rows, raw, plans, stores, commands, inventory = [], [], [], [], [], []
    pool = output / 'payload_blobs'
    pool.mkdir()
    provenance = []
    for name, data in [('interrupted_logistic', old), ('forest_rerun', new)]:
        id_map = {}
        for command in data['commands']:
            record = copy.deepcopy(command)
            id_map[record['id']] = len(commands)
            record.update(original_id=record['id'], id=len(commands), source_attempt=name)
            commands.append(record)
        for record in data['raw']:
            record = copy.deepcopy(record)
            record['source_attempt'] = name
            if 'native_checkout_receipt' in record:
                receipt = record['native_checkout_receipt']
                receipt['command_receipt_id'] = id_map[receipt['command_receipt_id']]
            raw.append(record)
        for plan in data['plans']:
            plan = copy.deepcopy(plan)
            for receipt in plan['diagnostics'].get('native_checkout_receipts', {}).values():
                receipt['command_receipt_id'] = id_map[receipt['command_receipt_id']]
            plans.append(plan)
        rows.extend(data['rows'])
        stores.extend(data['stores'])
        selected = {blob for store in data['stores'] for blob in store['selected']}
        for blob in selected:
            destination = pool / (blob + '.pkl')
            if not destination.exists():
                shutil.copy2(data['directory'] / 'payload_blobs' / destination.name, destination)
        for capture in sorted(data['captures']):
            shutil.copytree(data['directory'] / 'captures' / capture, output / 'captures' / capture)
        inventory.extend(row for row in json.loads((data['directory'] / 'capture_inventory.json').read_text()) if row['capture_id'] in data['captures'])
        provenance.append(dict(source_attempt=name, source_directory=str(data['directory']),
            source_hashes={path.name: sha(path) for path in data['directory'].iterdir() if path.is_file() and path.suffix in ('.csv', '.json', '.jsonl', '.gz')},
            included_captures=sorted(data['captures'])))
    if len(rows) != protocol['expected_summary_rows'] or len(raw) != protocol['expected_recovery_requests']:
        raise RuntimeError('Merged study does not satisfy the fixed full grid')
    with (output / 'summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with gzip.open(output / 'raw.jsonl.gz', 'wt', compresslevel=6) as handle:
        for row in raw:
            handle.write(json.dumps(row) + '\n')
    for stem, values in [('planner_records', plans), ('store_index', stores), ('native_commands', commands), ('capture_inventory', inventory)]:
        (output / (stem + '.json')).write_text(json.dumps(values, indent=2) + '\n')
    receipt = dict(status='PASS', rule='Reuse all complete logistic captures and rerun every forest capture without outcome selection',
        attempts=provenance, audits=receipts, summary_rows=len(rows), raw_requests=len(raw),
        native_checkout_commands=sum(row['command'][1:4] == ['-m', 'dvc', 'checkout'] for row in commands),
        original_interruption=json.loads((original / 'INTERRUPTED.json').read_text()),
        qualification='Original missing raw timings were not reconstructed. Source-attempt native receipt IDs were remapped with original IDs preserved.')
    (output / 'resumption_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    archive = output / 'stores_deduplicated.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as handle:
        for name in ('payload_blobs', 'captures', 'store_index.json'):
            handle.add(output / name, arcname=name)
    (output / 'store_compaction.json').write_text(json.dumps(dict(logical_stores=len(stores),
        unique_payload_blobs=len(list(pool.iterdir())), unique_payload_bytes=sum(path.stat().st_size for path in pool.iterdir()),
        archive_bytes=archive.stat().st_size, archive_sha256=sha(archive),
        method='Exact SHA-256 payload pool with every store membership and manifest'), indent=2) + '\n')
    # Preserve all interrupted measurements, including excluded partial forest rows.
    with tarfile.open(output / 'interrupted_attempt_evidence.tar.gz', 'w:gz') as handle:
        for path in original.iterdir():
            if path.is_file() or path.name in ('source_snapshot', 'captures'):
                handle.add(path, arcname=path.name)
    print(json.dumps({key: value for key, value in receipt.items() if key not in ('attempts', 'original_interruption')}, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', required=True)
    parser.add_argument('--rerun')
    parser.add_argument('--output', required=True)
    parser.add_argument('--protocol', default='configs/eyeai_rebuild_oct15.json')
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    merge(args.original, args.rerun, args.output, args.protocol, args.audit_only)
