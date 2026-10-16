"""Complete fixed-grid retinal retention benchmark with raw disk replay logs."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import numpy as np
from threadpoolctl import threadpool_limits

from .capability_retention import contract, optimize, retained_bytes, restricted
from .core import Graph, canonical, digest, pack
from .eyeai_workflow import capture, capabilities_for, execute, target_view
from .robust_heuristics import fault_sets, select
from .scenario_retention import optimize as scenario_optimize
from .witness import WitnessRestorer, certificate


POLICIES = ('RecoverML_exact', 'robust_greedy', 'robust_local',
            'DVC_target_snapshots', 'DVC_all_stages')


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def command(arguments, cwd, log):
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(arguments, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    receipt = dict(id=len(log), command=arguments, cwd=str(cwd), started_utc=stamp,
        elapsed_s=time.perf_counter() - started, returncode=result.returncode,
        stdout=result.stdout, stderr=result.stderr)
    log.append(receipt)
    if result.returncode:
        raise RuntimeError('Native command failed: ' + json.dumps(receipt))
    return receipt


def version_ancestors(graph, targets):
    seen = set()
    def visit(node):
        if node in seen:
            return
        seen.add(node)
        for dependency in graph.nodes[node].deps:
            visit(dependency)
    for target in targets:
        visit(target)
    return {graph.nodes[node].blob for node in seen}


def native_snapshots(graph, mode, destination, pool, command_log):
    """Native DVC per-version snapshots, verified once and reused by faults."""
    destination.mkdir()
    python = sys.executable
    command([python, '-m', 'dvc', 'init', '--no-scm', '-q'], destination, command_log)
    command([python, '-m', 'dvc', 'config', 'cache.type', 'hardlink,copy'], destination, command_log)
    selected = set(graph.roots)
    folders = []
    version_blobs = {}
    for version, targets in graph.targets.items():
        blobs = ({graph.nodes[node].blob for node in targets} if mode == 'targets'
                 else version_ancestors(graph, targets))
        folder = destination / 'payload' / version
        folder.mkdir(parents=True)
        for blob in blobs:
            os.link(pool / (blob + '.pkl'), folder / (blob + '.pkl'))
        version_blobs[version] = blobs
        selected.update(blobs)
        folders.append('payload/' + version)
    command([python, '-m', 'dvc', 'add', '-q', *folders], destination, command_log)
    checkouts = {}
    for version, blobs in version_blobs.items():
        shutil.rmtree(destination / 'payload' / version)
        receipt = command([python, '-m', 'dvc', 'checkout', '-q', 'payload/' + version + '.dvc'],
                          destination, command_log)
        verified = []
        for blob in sorted(blobs):
            raw = (destination / 'payload' / version / (blob + '.pkl')).read_bytes()
            if digest(raw) != blob:
                raise RuntimeError('DVC native checkout hash mismatch')
            verified.append(blob)
        checkouts[version] = dict(command_receipt_id=receipt['id'],
            native_checkout_s=receipt['elapsed_s'], verified_blobs=verified)
    cache_files = [path for path in (destination / '.dvc' / 'cache').rglob('*') if path.is_file()]
    cache_bytes = sum(path.stat().st_size for path in cache_files)
    payload_bytes = sum(graph.sizes()[blob] for blob in selected - graph.roots)
    # DVC cache additionally includes directory manifests and shared roots in the all-stage policy.
    native_data = set().union(*version_blobs.values())
    native_payload_bytes = sum(graph.sizes()[blob] for blob in native_data)
    pointers = [destination / (folder + '.dvc') for folder in folders]
    return selected, dict(native_checkout_receipts=checkouts, native_cache_bytes=cache_bytes,
        native_unique_payload_bytes=native_payload_bytes,
        native_cache_object_overhead_bytes=cache_bytes - native_payload_bytes,
        native_pointer_bytes=sum(path.stat().st_size for path in pointers),
        normalized_selected_nonroot_bytes=payload_bytes,
        native_checkout_count=len(checkouts), native_DVC_version=__import__('dvc').__version__)


def materialize(graph, selected, destination, pool, caps, k):
    destination.mkdir(parents=True)
    (destination / 'blobs').mkdir()
    (destination / 'manifest.json').write_bytes(canonical(graph.manifest()))
    (destination / 'capability_contract.json').write_bytes(contract(caps, k))
    for blob in selected:
        os.link(pool / (blob + '.pkl'), destination / 'blobs' / (blob + '.pkl'))
    physical = sum(path.stat().st_size for path in destination.rglob('*') if path.is_file())
    if physical != retained_bytes(graph, selected, caps, k):
        raise RuntimeError('Common logical byte accounting differs from actual store bytes')
    return physical


def resource_now():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    io = {}
    path = Path('/proc/self/io')
    if path.is_file():
        for line in path.read_text().splitlines():
            key, value = line.split(':')
            io[key] = int(value.strip())
    return dict(process_cpu_s=usage.ru_utime + usage.ru_stime,
                max_rss_kib=usage.ru_maxrss, io=io)


def replay(graph, store, caps, fault, version):
    before = resource_now()
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).isoformat()
    error = None
    events = []
    actual = []
    try:
        view = restricted(graph, caps, fault)
        restorer = WitnessRestorer(view, store, replay_execute=execute)
        values = restorer.version(version)
        events = restorer.trace
        actual = [digest(pack(value)) for value in values]
        expected = [graph.nodes[node].blob for node in graph.targets[version]]
        exact = actual == expected
    except Exception as exc:
        exact = False
        error = type(exc).__name__ + ': ' + str(exc)
    elapsed = time.perf_counter() - started
    after = resource_now()
    return dict(started_utc=stamp, elapsed_s=elapsed,
        process_cpu_s=after['process_cpu_s'] - before['process_cpu_s'],
        max_rss_kib=after['max_rss_kib'],
        io_delta={key: after['io'][key] - before['io'].get(key, 0) for key in after['io']},
        exact=exact, actual_sha256=actual,
        expected_sha256=[graph.nodes[node].blob for node in graph.targets[version]],
        error=error, events=events)


def source_snapshot(output, protocol):
    source = output / 'source_snapshot'
    source.mkdir()
    root = Path(__file__).resolve().parents[2]
    files = list((root / 'src' / 'recoverml').glob('*.py'))
    files += [root / 'configs' / 'eyeai_rebuild_oct15.json', root / 'scripts' / 'download_stare.py',
              root / 'scripts' / 'analyze_eyeai.py', root / 'requirements.txt', root / 'pyproject.toml']
    hashes = {}
    for path in files:
        if path.is_file():
            relative = path.relative_to(root)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            hashes[str(relative)] = digest(path.read_bytes())
    atomic_json(output / 'source_hashes.json', hashes)
    atomic_json(output / 'protocol.json', protocol)


def run(output, dataset, config, preflight=False):
    output, dataset = Path(output), Path(dataset)
    if output.exists() and any(output.iterdir()):
        allowed = {'data_acquisition.json'}
        if set(path.name for path in output.iterdir()) - allowed:
            raise ValueError('Refuse to overwrite an existing experimental result directory')
    output.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(Path(config).read_text())
    if preflight:
        protocol.update(seeds=[3], estimators=['forest'], versions=[2], targets=['model_prediction'],
            availability=['legacy_removed'], expected_summary_rows=5, expected_recovery_requests=20,
            qualification='Preflight not a full grid')
    source_snapshot(output, protocol)
    command_log, inventory, plans, rows, stores = [], [], [], [], []
    pool = output / 'payload_blobs'
    pool.mkdir()
    raw = (output / 'raw.jsonl').open('w', buffering=1)
    plan_stream = (output / 'planner_records.jsonl').open('w', buffering=1)
    store_stream = (output / 'store_records.jsonl').open('w', buffering=1)
    writer = None
    summary = (output / 'summary.csv').open('w', newline='', buffering=1)
    with tempfile.TemporaryDirectory(prefix='recoverml-retina-') as temporary:
        scratch = Path(temporary)
        with threadpool_limits(limits=1):
            for estimator, seed, versions in itertools.product(protocol['estimators'], protocol['seeds'], protocol['versions']):
                capture_id = f'{estimator}_s{seed}_v{versions}'
                print('CAPTURE', capture_id, flush=True)
                graph, info = capture(dataset, estimator, seed, versions)
                for blob, value in graph.archive.items():
                    path = pool / (blob + '.pkl')
                    if not path.exists():
                        path.write_bytes(value)
                    if digest(path.read_bytes()) != blob:
                        raise RuntimeError('Global payload pool hash mismatch')
                capture_dir = output / 'captures' / capture_id
                capture_dir.mkdir(parents=True)
                (capture_dir / 'manifest.json').write_bytes(canonical(graph.manifest()))
                atomic_json(capture_dir / 'info.json', info)
                inventory.append(dict(capture_id=capture_id, **info))
                atomic_json(output / 'capture_inventory.json', inventory)
                # Capture payloads are not part of the replay graph and are not available to the restorer.
                graph.archive = {}
                for target_mode in protocol['targets']:
                    view = target_view(graph, target_mode)
                    native = {}
                    for policy, native_mode in [('DVC_target_snapshots', 'targets'), ('DVC_all_stages', 'all')]:
                        folder = scratch / (capture_id + '_' + target_mode + '_' + native_mode)
                        selected, native_info = native_snapshots(view, native_mode, folder, pool, command_log)
                        native[policy] = (selected, native_info)
                        atomic_json(output / 'native_commands.json', command_log)
                    for availability in protocol['availability']:
                        caps, k = capabilities_for(view, availability)
                        faults = fault_sets(caps, k)
                        budget = retained_bytes(view, view.candidates, caps, k)
                        for policy in POLICIES:
                            started = time.perf_counter()
                            cpu_start = time.process_time()
                            if policy == 'RecoverML_exact':
                                selected, status, diagnostic = optimize(view, caps, k, time_limit_s=30.)
                                planning_s = time.perf_counter() - started
                                planning_cpu_s = time.process_time() - cpu_start
                                independent_started = time.perf_counter()
                                independent, independent_status, independent_info = scenario_optimize(view, caps, k, time_limit_s=30.)
                                if status != 'ok' or independent_status != 'ok' or not diagnostic['storage_optimal']:
                                    raise RuntimeError('Exact solver could not prove the declared condition')
                                if retained_bytes(view, selected, caps, k) != retained_bytes(view, independent, caps, k):
                                    raise RuntimeError('The two exact formulations disagree')
                                diagnostic['independent_exact_status'] = independent_status
                                diagnostic['independent_exact'] = independent_info
                                diagnostic['independent_validation_s'] = time.perf_counter() - independent_started
                            elif policy in ('robust_greedy', 'robust_local'):
                                selected, diagnostic = select(view, caps, k, budget,
                                    local_improvement=policy == 'robust_local')
                                status = 'ok' if diagnostic['robust_certified'] else 'partial'
                            else:
                                selected, diagnostic = native[policy]
                                status = 'ok'
                            if policy != 'RecoverML_exact':
                                planning_s = time.perf_counter() - started
                                planning_cpu_s = time.process_time() - cpu_start
                            key = f'{capture_id}__{target_mode}__{availability}__{policy}'
                            if not all(certificate(restricted(view, caps, fault), selected)['complete'] for fault in faults):
                                raise RuntimeError('Selected store fails the common recovery contract')
                            store = scratch / 'stores' / key
                            actual_bytes = materialize(view, selected, store, pool, caps, k)
                            disk = Graph.read(store / 'manifest.json')
                            records = []
                            for fault in faults:
                                for version in disk.targets:
                                    measurement = replay(disk, store, caps, fault, version)
                                    record = dict(condition_id=key, capture_id=capture_id,
                                        estimator=estimator, seed=seed, versions=versions,
                                        target_mode=target_mode, availability=availability, policy=policy,
                                        fault=list(fault), version=version, **measurement)
                                    if policy.startswith('DVC_'):
                                        record['native_checkout_receipt'] = diagnostic['native_checkout_receipts'][version]
                                        record['native_checkout_reused_across_faults'] = True
                                        record['elapsed_scope'] = 'Actual selected snapshot file reads and exact decoding; native CLI cost separate'
                                    else:
                                        record['elapsed_scope'] = 'Actual disk load or operator replay including exact verification'
                                    raw.write(json.dumps(record) + '\n')
                                    records.append(record)
                            latencies = [record['elapsed_s'] for record in records]
                            row = dict(condition_id=key, capture_id=capture_id, estimator=estimator,
                                seed=seed, versions=versions, target_mode=target_mode,
                                availability=availability, policy=policy, status=status,
                                retained_bytes=actual_bytes, selected_payload_bytes=sum(view.sizes()[b] for b in selected),
                                metadata_bytes=actual_bytes - sum(view.sizes()[b] for b in selected),
                                selected_blobs=len(selected), total_blobs=len(view.candidates),
                                planning_s=planning_s, planning_cpu_s=planning_cpu_s,
                                requests=len(records), exact=sum(record['exact'] for record in records),
                                errors=sum(record['error'] is not None for record in records),
                                mean_restore_s=float(np.mean(latencies)), p50_s=float(np.quantile(latencies, .5)),
                                p90_s=float(np.quantile(latencies, .9)), p99_s=float(np.quantile(latencies, .99)),
                                recovery_cpu_s=sum(record['process_cpu_s'] for record in records),
                                native_cache_bytes=diagnostic.get('native_cache_bytes', ''),
                                native_unique_payload_bytes=diagnostic.get('native_unique_payload_bytes', ''),
                                native_cache_object_overhead_bytes=diagnostic.get('native_cache_object_overhead_bytes', ''),
                                native_pointer_bytes=diagnostic.get('native_pointer_bytes', ''),
                                native_checkout_count=diagnostic.get('native_checkout_count', 0),
                                native_checkout_s=sum(r['native_checkout_s'] for r in diagnostic.get('native_checkout_receipts', {}).values()))
                            rows.append(row)
                            if writer is None:
                                writer = csv.DictWriter(summary, fieldnames=list(row))
                                writer.writeheader()
                            writer.writerow(row)
                            summary.flush()
                            plans.append(dict(condition_id=key, selected=sorted(selected),
                                planning_s=planning_s, planning_cpu_s=planning_cpu_s, diagnostics=diagnostic))
                            stores.append(dict(condition_id=key, manifest=view.manifest(),
                                capabilities=caps, k=k, selected=sorted(selected)))
                            # Append complete rows rather than repeatedly rewriting large ledgers.
                            plan_stream.write(json.dumps(plans[-1]) + '\n')
                            store_stream.write(json.dumps(stores[-1]) + '\n')
                            atomic_json(output / 'progress.json', dict(completed_rows=len(rows),
                                expected_rows=protocol['expected_summary_rows'], last_condition=key,
                                raw_requests=sum(row['requests'] for row in rows)))
                            print('ROW', len(rows), key, actual_bytes, row['exact'], '/', row['requests'], flush=True)
                            shutil.rmtree(store)
                    # Native caches are only retained during measurements. Their full commands and hashes remain.
                    for mode in ('targets', 'all'):
                        shutil.rmtree(scratch / (capture_id + '_' + target_mode + '_' + mode))
    summary.close()
    raw.close()
    plan_stream.close()
    store_stream.close()
    atomic_json(output / 'planner_records.json', plans)
    atomic_json(output / 'store_index.json', stores)
    # Rewrite the entire final CSV from the complete in-memory ledger before packaging.
    with (output / 'summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    atomic_json(output / 'native_commands.json', command_log)
    if len(rows) != protocol['expected_summary_rows'] or sum(row['requests'] for row in rows) != protocol['expected_recovery_requests']:
        raise RuntimeError('The observed grid does not match the fixed protocol')
    with (output / 'raw.jsonl').open('rb') as source, gzip.open(output / 'raw.jsonl.gz', 'wb', compresslevel=6) as destination:
        shutil.copyfileobj(source, destination)
    # Keep the plaintext during the running session; commit the compact exact copy.
    archive = output / 'stores_deduplicated.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        tar.add(pool, arcname='payload_blobs')
        tar.add(output / 'captures', arcname='captures')
        tar.add(output / 'store_index.json', arcname='store_index.json')
    atomic_json(output / 'store_compaction.json', dict(logical_stores=len(stores),
        unique_payload_blobs=len(list(pool.glob('*.pkl'))),
        unique_payload_bytes=sum(path.stat().st_size for path in pool.glob('*.pkl')),
        archive_bytes=archive.stat().st_size, archive_sha256=digest(archive.read_bytes()),
        method='Each original SHA-256 payload stored once; per-store membership and original manifest retained'))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--dataset', default='work/stare')
    parser.add_argument('--config', default='configs/eyeai_rebuild_oct15.json')
    parser.add_argument('--preflight', action='store_true')
    arguments = parser.parse_args()
    run(arguments.output, arguments.dataset, arguments.config, arguments.preflight)
