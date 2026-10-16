"""Run the fixed exploratory multiview challenge and retain every outcome."""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import random
import resource
import statistics
import subprocess
import tarfile
import tempfile
import time

import numpy as np
from threadpoolctl import threadpool_limits

from recoverml.capability_retention import contract, retained_bytes, restricted
from recoverml.core import Graph, RestoreError, digest, environment, pack, write_store
from recoverml.dag_retention import optimize as cut_exact
from recoverml.robust_retention import optimize as auto_exact
from recoverml.scenario_retention import optimize as expanded
from recoverml.robust_heuristics import fault_sets, select as heuristic
from recoverml.published_materializers import load_source, select as hyppo
from recoverml.helix_materializer import select as helix
from recoverml.multiview_workflow import capture, execute
from recoverml.witness import certificate, WitnessRestorer


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


class CheckpointTrace:
    """Close a complete gzip member per history so progress survives a reset."""
    def __init__(self, path):
        self.path = path
        self.stream = None

    def __enter__(self):
        return self

    def write(self, value):
        if self.stream is None:
            self.stream = gzip.open(self.path, 'at')
        return self.stream.write(value)

    def checkpoint(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def __exit__(self, *exception):
        self.checkpoint()


def io_counters():
    try:
        return {k: int(v) for k, v in (line.split(':') for line in Path('/proc/self/io').read_text().splitlines())}
    except (OSError, ValueError):
        return {}


def manual_frontier(g, caps, k):
    targets = {g.nodes[t].blob for ts in g.targets.values() for t in ts}
    options = [g.roots | targets, g.roots | {n.blob for n in g.nodes.values() if n.op == 'view_standardize'}]
    concats = {n.blob for n in g.nodes.values() if n.op == 'view_concat'}
    if concats:
        options.append(g.roots | concats)
    feasible = [s for s in options if all(certificate(restricted(g, caps, f), s)['complete']
                                       for f in fault_sets(caps, k))]
    return min(feasible, key=lambda s: (retained_bytes(g, s, caps, k), sorted(s)))


def execute_stores(g, caps, k, selections, output, trace):
    groups = {}
    for method, selected in selections.items():
        key = digest('\n'.join(sorted(selected)).encode())
        groups.setdefault(key, dict(selected=selected, methods=[]))['methods'].append(method)
    receipts = {}
    for key, group in groups.items():
        selected = group['selected']; times = []; exact = blocked = unexpected = 0
        with tempfile.TemporaryDirectory(prefix='recoverml_multiview_') as temp:
            store = Path(temp) / 'store'
            write_store(g, selected, store)
            (store / 'capability_contract.json').write_bytes(contract(caps, k))
            physical = sum(p.stat().st_size for p in store.rglob('*') if p.is_file())
            if physical != retained_bytes(g, selected, caps, k):
                raise RuntimeError('Store accounting failed')
            for lost in fault_sets(caps, k):
                forbidden = {tuple(g.nodes[n].params['columns']) for n, groupname in caps.items() if groupname in lost}

                def guarded_execute(op, values, params):
                    if op == 'view_standardize' and tuple(params['columns']) in forbidden:
                        raise RestoreError('Disabled preprocessing was dispatched')
                    return execute(op, values, params)

                for version, targets in g.targets.items():
                    disk = Graph.read(store / 'manifest.json')
                    view = restricted(disk, caps, lost)
                    expected = certificate(view, selected)['version_coverage'][version]
                    timestamp = time.time_ns(); clock = time.perf_counter(); cpu = time.process_time()
                    before_io = io_counters(); error = None; ok = False; restorer = None
                    try:
                        restorer = WitnessRestorer(view, store, replay_execute=guarded_execute)
                        values = restorer.version(version)
                        ok = all(pack(value) == g.archive[g.nodes[t].blob] for value, t in zip(values, targets))
                    except Exception as exc:
                        error = repr(exc)
                    elapsed = time.perf_counter() - clock
                    after_io = io_counters(); times.append(elapsed)
                    unexpected += int(expected != ok or (expected and error is not None))
                    exact += int(ok); blocked += int(not ok and not expected)
                    record = dict(history=output.name, store_key=key, methods=group['methods'], version=version,
                        disabled=list(lost), start_timestamp_ns=timestamp, elapsed_s=elapsed,
                        cpu_s=time.process_time()-cpu, expected_recoverable=expected, exact=ok, error=error,
                        io_delta={name: after_io.get(name, 0)-before_io.get(name, 0) for name in after_io},
                        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        target_sha256=[g.nodes[t].blob for t in targets],
                        operations=[] if restorer is None else restorer.trace)
                    trace.write(json.dumps(record, allow_nan=False) + '\n')
            dump(output / (key + '.json'), dict(store_key=key, methods=group['methods'], selected=sorted(selected),
                physical_bytes=physical, exact=exact, expected_blocked=blocked, unexpected=unexpected,
                requests=len(times), p50_s=float(np.percentile(times, 50)), p90_s=float(np.percentile(times, 90)),
                p99_s=float(np.percentile(times, 99))))
            receipts[key] = dict(exact=exact, expected_blocked=blocked, unexpected=unexpected, requests=len(times),
                p50_s=float(np.percentile(times, 50)), p90_s=float(np.percentile(times, 90)),
                p99_s=float(np.percentile(times, 99)))
    return receipts


def run(output, protocol, hyppo_cache):
    output.mkdir(parents=True, exist_ok=False)
    protocol_raw = protocol.read_bytes(); config = json.loads(protocol_raw)
    (output / 'protocol.json').write_bytes(protocol_raw)
    source_paths = sorted(Path('src/recoverml').glob('*.py')) + [Path(__file__), protocol]
    hashes = {str(p): digest(p.read_bytes()) for p in source_paths}
    with tarfile.open(output / 'source_snapshot.tar.gz', 'w:gz') as archive:
        for p in source_paths: archive.add(p, arcname=str(p))
    dump(output / 'run_start.json', dict(timestamp_ns=time.time_ns(), source_sha256=hashes,
        protocol_sha256=digest(protocol_raw), commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        environment=environment(), exploratory=True,
        runtime_accounting='Identical selected stores share one explicit measured request ledger and are not counted as independent executions'))
    module = load_source(hyppo_cache); rows = []; records = []; captures = []; errors = []
    k = config['maximum_lost_groups']
    checkpoint_counts = Counter()
    with CheckpointTrace(output / 'execution_traces.jsonl.gz') as trace, threadpool_limits(limits=1):
        for dataset in config['datasets']:
            for seed in config['seeds']:
                for versions in config['versions']:
                    for concat in config['concat_materialized']:
                        history = f'{dataset}-s{seed}-v{versions}-concat{int(concat)}'
                        case = output / 'cases' / history; case.mkdir(parents=True)
                        start = time.perf_counter()
                        if config.get('capture_input'):
                            origin = Path(config['capture_input']) / history
                            g = Graph.read(origin / 'manifest.json')
                            info = json.loads((origin / 'info.json').read_text())
                            for blob in g.candidates:
                                raw = (origin / 'blobs' / (blob + '.pkl')).read_bytes()
                                if digest(raw) != blob or len(raw) != g.sizes()[blob]:
                                    raise RuntimeError('Captured input integrity failed')
                                g.archive[blob] = raw
                            caps = {n.id: 'shared_standardization_entrypoint' for n in g.nodes.values()
                                    if n.op == 'view_standardize'}
                            info = dict(info, source_manifest_sha256=digest((origin/'manifest.json').read_bytes()),
                                        reused_original_capture=True, capability_grouping=config['capability_grouping'])
                        else:
                            g, caps, info = capture(dataset, seed, versions, concat)
                        captures.append(dict(history=history, capture_s=time.perf_counter()-start, **info))
                        write_store(g, g.candidates, output / 'captures' / history)
                        dump(output / 'captures' / history / 'info.json', info)
                        chosen, status, diag = cut_exact(g, caps, k)
                        if status != 'ok': raise RuntimeError('Fixed workflow is outside DAG subclass')
                        optimum = retained_bytes(g, chosen, caps, k)
                        full = retained_bytes(g, g.candidates, caps, k)
                        fixed = retained_bytes(g, g.roots, caps, k)
                        selections = {}; timing = {m: [] for m in config['methods']}; diagnostics = {}
                        for repeat in range(config['timing_repetitions']):
                            methods = list(config['methods']); random.Random(seed+versions+repeat).shuffle(methods)
                            for method in methods:
                                start = time.perf_counter()
                                if method == 'RecoverML_exact':
                                    selected, status, d = auto_exact(g, caps, k)
                                elif method == 'scenario_exact':
                                    selected, status, d = expanded(g, caps, k, time_limit_s=config['solver_time_limit_s'])
                                elif method.startswith('robust_'):
                                    selected, d = heuristic(g, caps, k, full, method == 'robust_local'); status = 'heuristic'
                                elif method == 'manual_best_frontier':
                                    selected = manual_frontier(g, caps, k); status = 'manual_retention_control'; d = {}
                                elif method.startswith('HYPPO'):
                                    selected = hyppo(g, optimum-fixed, module, method == 'HYPPO_frequency'); status = 'published_component'; d = {}
                                elif method == 'HELIX_rule':
                                    selected, d = helix(g, optimum-fixed, config['helix_read_MiB_s']*1024**2); status = 'published_rule'
                                else:
                                    selected = g.roots | {g.nodes[t].blob for ts in g.targets.values() for t in ts}
                                    status = 'snapshot'; d = {}
                                elapsed = time.perf_counter()-start
                                timing[method].append(elapsed)
                                if method in selections and selected != selections[method]:
                                    raise RuntimeError('Selection changed across timing repetitions')
                                selections[method] = selected; diagnostics[method] = dict(status=status, detail=d)
                                records.append(dict(history=history, method=method, repetition=repeat,
                                    timestamp_ns=time.time_ns(), planning_s=elapsed, retained_bytes=retained_bytes(g, selected, caps, k),
                                    selected=sorted(selected), **diagnostics[method]))
                                if method in ('RecoverML_exact', 'scenario_exact') and (status != 'ok' or retained_bytes(g, selected, caps, k) != optimum):
                                    raise RuntimeError('Independent exact formulations disagree')
                        receipts = execute_stores(g, caps, k, selections, case, trace)
                        trace.checkpoint()
                        for receipt in receipts.values():
                            for name in ('requests', 'exact', 'expected_blocked', 'unexpected'):
                                checkpoint_counts[name] += receipt[name]
                        for method, selected in selections.items():
                            key = digest('\n'.join(sorted(selected)).encode()); receipt = receipts[key]
                            robust = all(certificate(restricted(g, caps, fault), selected)['complete'] for fault in fault_sets(caps, k))
                            row = dict(history=history, dataset=dataset, seed=seed, versions=versions, concat_materialized=concat,
                                method=method, retained_bytes=retained_bytes(g, selected, caps, k), exact_minimum_bytes=optimum,
                                fully_recoverable=robust, planning_median_s=statistics.median(timing[method]),
                                store_key=key, runtime_evidence_shared=True, **receipt)
                            if receipt['unexpected']: errors.append(dict(history=history, method=method, error='unexpected runtime outcome'))
                            rows.append(row)
                        dump(output / 'capture_inventory.json', captures)
                        with (output / 'summary.csv').open('w', newline='') as handle:
                            writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
                        with gzip.open(output / 'planner_records.json.gz', 'wt') as handle: json.dump(records, handle)
                        dump(output / 'errors.json', errors)
                        dump(output / 'checkpoint.json', dict(status='RUNNING_NOT_FINAL',
                            timestamp_ns=time.time_ns(), completed_histories=len(captures),
                            planned_histories=len(config['datasets'])*len(config['seeds'])*len(config['versions'])*len(config['concat_materialized']),
                            conditions=len(rows), planning_calls=len(records), actual_runtime=dict(checkpoint_counts),
                            closed_trace_sha256=digest((output/'execution_traces.jsonl.gz').read_bytes()),
                            planner_sha256=digest((output/'planner_records.json.gz').read_bytes()),
                            source_changed=[str(p) for p in source_paths if digest(p.read_bytes()) != hashes[str(p)]],
                            errors=errors))
                        print(json.dumps(dict(history=history, conditions=len(rows), exact_bytes=optimum,
                            local_bytes=retained_bytes(g, selections['robust_local'], caps, k),
                            local_planning_s=statistics.median(timing['robust_local']), errors=len(errors))), flush=True)
    changed = [str(p) for p in source_paths if digest(p.read_bytes()) != hashes[str(p)]]
    if changed: errors.append(dict(error='source_changed', paths=changed))
    # Close raw streams before hashing. Preserve every capture in a compact archive.
    with tarfile.open(output / 'captures.tar.gz', 'w:gz') as archive:
        archive.add(output / 'captures', arcname='captures')
    actual = Counter()
    with gzip.open(output / 'execution_traces.jsonl.gz', 'rt') as trace:
        for line in trace:
            r = json.loads(line); actual['requests'] += 1; actual['exact'] += int(r['exact'])
            actual['expected_blocked'] += int(not r['expected_recoverable'] and not r['exact'])
            actual['unexpected'] += int(r['expected_recoverable'] != r['exact'])
    dump(output / 'run_end.json', dict(status='PASS' if not errors else 'FAIL', timestamp_ns=time.time_ns(),
        histories=len(captures), conditions=len(rows), planning_calls=len(records), actual_runtime=dict(actual),
        source_changed=changed, errors=errors, source_sha256=hashes,
        closed_evidence_sha256={p.name: digest(p.read_bytes()) for p in output.iterdir() if p.is_file()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('configs/multiview_shared_followup_oct16.json'))
    parser.add_argument('--hyppo-cache', type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.protocol, args.hyppo_cache)
