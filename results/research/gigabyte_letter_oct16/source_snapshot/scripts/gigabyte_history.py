#!/usr/bin/env python3
"""Fixed, disk-backed UCI Letter forest history; no padded model artifacts.

The uncompressed canonical model contract is the primary identity. Gzip and
native sklearn pickle sizes are separate controls, not interchangeable claims.
Use the small preflight protocol before the frozen 16-model main protocol.
"""
from __future__ import annotations
import argparse
import csv
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import pickle
import resource
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
import io

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from threadpoolctl import threadpool_limits

from recoverml.core import Graph, canonical, digest, environment, pack
from recoverml.scientific_workflows import execute, implementation_sha256, caps_for
from recoverml.component_retention import optimize as exact
from recoverml.scenario_retention import optimize as scenario
from recoverml.robust_heuristics import fault_sets, select as heuristic
from recoverml.capability_retention import contract, retained_bytes, restricted
from recoverml.witness import certificate, WitnessRestorer

DATA_URL = 'https://archive.ics.uci.edu/static/public/59/letter+recognition.zip'
DATA_SHA256 = '2b89f3602cf768d3c8355267d2f13f2417809e101fc2b5ceee10db19a60de6e2'
METHODS = ['RecoverML_exact', 'scenario_exact', 'robust_greedy', 'robust_local', 'target_snapshots']


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def compress(source, destination):
    with source.open('rb') as raw, destination.open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, compresslevel=6, mtime=0) as zipped:
            shutil.copyfileobj(raw, zipped, length=1024 * 1024)
    return dict(gzip_bytes=destination.stat().st_size, gzip_sha256=file_sha(destination))


def obtain_data(path):
    if not path.exists():
        archive = urllib.request.urlopen(DATA_URL, timeout=120).read()
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            name = next(n for n in zipped.namelist() if n.endswith('letter-recognition.data'))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(zipped.read(name))
    if file_sha(path) != DATA_SHA256:
        raise RuntimeError('Official UCI Letter data hash mismatch')
    return dict(url=DATA_URL, sha256=DATA_SHA256, bytes=path.stat().st_size,
                citation='Slate, D. (1991). Letter Recognition. UCI ML Repository. doi:10.24432/C5ZP40',
                license='CC BY 4.0', original_rows=20000, original_features=16, original_classes=26)


def frozen_sources():
    root = Path(__file__).resolve().parents[1]
    paths = list((root / 'src' / 'recoverml').glob('*.py')) + [Path(__file__).resolve(), root / 'scripts' / 'analyze_gigabyte_history.py']
    return {str(p.relative_to(root)): file_sha(p) for p in paths if p.exists()}


def capture(protocol, data, output, work):
    blobs = work / 'capture_blobs'; zipped = work / 'gzip_blobs'
    native = work / 'native_pickle'; native.mkdir(parents=True, exist_ok=False)
    blobs.mkdir(); zipped.mkdir()
    array = np.loadtxt(data, dtype=str, delimiter=',')
    if array.shape != (20000, 17):
        raise RuntimeError('The study requires every official UCI Letter row')
    x = np.ascontiguousarray(array[:, 1:].astype(np.float64))
    y = np.ascontiguousarray(np.array([ord(v) - ord('A') for v in array[:, 0]], dtype=np.int64))
    if len(np.unique(y)) != 26 or x.shape != (20000, 16):
        raise RuntimeError('Dataset dimensions/classes mismatch')
    graph = Graph(); values = {}; inventory = {}; model_records = []
    implementation = implementation_sha256()

    def add(op, dependencies, parameters, scope, *, value=None, mandatory=False, version=0, keep=False):
        params = dict(parameters, implementation_sha256=implementation)
        clock = time.perf_counter()
        if value is None:
            value = execute(op, [values[d] for d in dependencies], params)
        nid = graph.add(op, dependencies, params, value, not mandatory, scope,
                        time.perf_counter() - clock, version, mandatory=mandatory)
        node = graph.nodes[nid]
        raw = graph.archive.pop(node.blob)
        if node.blob not in inventory:
            rawpath = blobs / (node.blob + '.pkl'); rawpath.write_bytes(raw)
            inventory[node.blob] = dict(blob=node.blob, bytes=len(raw),
                **compress(rawpath, zipped / (node.blob + '.pkl.gz')))
        if graph.archive:
            raise RuntimeError('Capture archive must not accumulate historical model payloads')
        if keep:
            values[nid] = value
        del raw
        return nid, value

    rx, _ = add('input', [], dict(dataset='UCI_Letter_Recognition', kind='x'), 'source', value=x, mandatory=True, keep=True)
    ry, _ = add('input', [], dict(dataset='UCI_Letter_Recognition', kind='y'), 'source', value=y, mandatory=True, keep=True)
    split, indices = add('scientific_split', [rx, ry], dict(seed=protocol['split_seed'], classification=True), 'membership', keep=True)
    if protocol['test_fraction'] != .25 or len(indices[0]) != 15000 or len(indices[1]) != 5000:
        raise RuntimeError('Actual fixed scientific_split must match the declared 25% stratified test split')
    current = rx
    for estimator, parameters in [('minmax', {}), ('select_chi2', {'k': 12})]:
        fitted, _ = add('scientific_fit_transformer', [current, ry, split],
                        dict(estimator=estimator, parameters=parameters), 'preprocessing', keep=True)
        current, _ = add('scientific_transform', [current, fitted],
                         dict(estimator=estimator, parameters=parameters), 'preprocessing', keep=True)
    features = current
    for version, configuration in enumerate(protocol['configurations']):
        parameters = dict(configuration, n_jobs=1)
        clock = time.perf_counter()
        model_id, model = add('scientific_train', [features, ry, split],
                              dict(estimator='forest', parameters=parameters), 'model', version=version)
        if not isinstance(model, RandomForestClassifier):
            raise RuntimeError('Native forest diagnostic requires the actual fitted sklearn estimator')
        # Native protocol-5 pickle is a representation diagnostic only. Its
        # object-reference identities are not our canonical model identity.
        native_path = native / (str(version) + '.pkl')
        with native_path.open('wb') as stream:
            pickle.dump(model, stream, protocol=5)
        with native_path.open('rb') as stream:
            native_restored = pickle.load(stream)
        native_roundtrip = np.array_equal(model.predict(values[features][indices[1]]), native_restored.predict(values[features][indices[1]]))
        del native_restored
        if not native_roundtrip:
            raise RuntimeError('Native pickle roundtrip predictions differ')
        native_record = dict(native_pickle_roundtrip_predictions_exact=bool(native_roundtrip), native_pickle_bytes=native_path.stat().st_size,
                             native_pickle_sha256=file_sha(native_path),
                             **{'native_' + key: value for key, value in compress(native_path, native / (str(version) + '.pkl.gz')).items()})
        values[model_id] = model
        prediction_id, prediction = add('scientific_predict', [model_id, features, split],
                                        dict(estimator='forest'), 'prediction', version=version)
        graph.targets[str(version)] = [model_id, prediction_id]
        quality = float(accuracy_score(y[indices[1]], prediction))
        model_records.append(dict(version=version, parameters=parameters, accuracy=quality,
             model_node=model_id, prediction_node=prediction_id,
             model_blob=graph.nodes[model_id].blob, prediction_blob=graph.nodes[prediction_id].blob,
             canonical_model_bytes=graph.nodes[model_id].size,
             canonical_prediction_bytes=graph.nodes[prediction_id].size,
             tree_count=len(model.estimators_), tree_node_count=sum(t.tree_.node_count for t in model.estimators_),
             capture_s=time.perf_counter()-clock, native_prediction_check=True, **native_record))
        values.pop(model_id); del model, prediction
        gc.collect()
        dump(output / 'capture_progress.json', dict(completed_models=len(model_records), expected_models=len(protocol['configurations']),
             model_records=model_records, unique_payload_bytes=sum(i['bytes'] for i in inventory.values())))
        print(json.dumps(dict(phase='capture', version=version, accuracy=quality,
             canonical_model_bytes=graph.nodes[model_id].size, total_payload_bytes=sum(i['bytes'] for i in inventory.values()))), flush=True)
    if len({r['model_blob'] for r in model_records}) != len(model_records):
        raise RuntimeError('A model configuration produced duplicate canonical bytes')
    (work / 'manifest.json').write_bytes(canonical(graph.manifest()))
    (output / 'manifest.json').write_bytes(canonical(graph.manifest()))
    dump(output / 'blob_inventory.json', inventory)
    dump(output / 'capture_inventory.json', dict(dataset='UCI Letter Recognition', rows=20000, features=16,
          classes=26, train_rows=15000, test_rows=5000, transformed_features=12,
          all_rows_used=True, training_partition_only_fit=True, selected_configurations=protocol['configurations'],
          no_padding=True, no_duplicate_model_artifacts=True, original_capture_archive_empty=not graph.archive,
          implementation_sha256=implementation, models=model_records,
          qualification='A fixed constructed CPU hyperparameter history on a new public dataset; not an independently collected production history'))
    return graph, inventory, model_records


def link_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copyfile(source, destination)


def native_dvc(graph, chosen, blobs, work, output):
    records = []
    with tempfile.TemporaryDirectory(prefix='recoverml_letter_dvc_') as temporary:
        base = Path(temporary)
        def run(arguments):
            clock = time.perf_counter(); ns = time.time_ns()
            completed = subprocess.run(arguments, cwd=base, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            records.append(dict(command=arguments, returncode=completed.returncode, stdout=completed.stdout,
                  stderr=completed.stderr, elapsed_s=time.perf_counter()-clock, start_timestamp_ns=ns, end_timestamp_ns=time.time_ns()))
            dump(output / 'native_dvc_commands.json', records)
            if completed.returncode:
                raise RuntimeError('Native DVC command failed: ' + repr(arguments))
        dvc = str(Path(sys.executable).with_name('dvc'))
        run([dvc, 'init', '--no-scm']); run([dvc, 'config', 'cache.type', 'hardlink'])
        targets = base / 'snapshots'; targets.mkdir()
        expected = {}
        for blob in sorted(chosen):
            path = targets / (blob + '.pkl'); link_file(blobs / (blob + '.pkl'), path)
            expected[path.name] = dict(sha256=blob, bytes=graph.sizes()[blob])
        run([dvc, 'add', 'snapshots'])
        shutil.rmtree(targets)
        absent = not targets.exists()
        if not absent:
            raise RuntimeError('DVC checkout missing-before guard failed')
        run([dvc, 'checkout', 'snapshots.dvc'])
        actual = {p.name: dict(sha256=file_sha(p), bytes=p.stat().st_size) for p in targets.iterdir() if p.is_file()}
        if actual != expected:
            raise RuntimeError('Native DVC checkout dictionary/hash mismatch')
        cache = base / '.dvc' / 'cache'
        cache_files = list(cache.rglob('*'))
        cache_bytes = sum(p.stat().st_size for p in cache_files if p.is_file())
        pointer_bytes = (base / 'snapshots.dvc').stat().st_size
        result = dict(status='PASS', missing_before_checkout=absent, expected=expected, actual=actual,
               physical_files_checked=len(actual), unique_snapshot_payload_bytes=sum(r['bytes'] for r in expected.values()),
               cache_object_logical_bytes=cache_bytes, pointer_file_bytes=pointer_bytes,
               hardlinks_requested=True, commands=len(records),
               qualification='One native DVC add/delete/checkout of all unique canonical target files; startup is separate from in-process recovery')
        dump(output / 'native_dvc_report.json', result)
        return result


def evaluate(graph, inventory, protocol, output, work):
    blobs = work / 'capture_blobs'; plans = []; structural = []; store_records = {}; rows = []
    targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    selected_snapshot = graph.roots | targets
    with gzip.open(output / 'execution_traces.jsonl.gz', 'wt') as stream:
        for scope in protocol['capability_scopes']:
            caps = caps_for(graph, scope); k = 1; budget = retained_bytes(graph, selected_snapshot, caps, k)
            faultscenarios = fault_sets(caps, k)
            for method in METHODS:
                clock = time.perf_counter()
                if method == 'RecoverML_exact':
                    chosen, status, diagnostic = exact(graph, caps, k, time_limit_s=protocol['solver_time_limit_s'])
                elif method == 'scenario_exact':
                    chosen, status, diagnostic = scenario(graph, caps, k, time_limit_s=protocol['solver_time_limit_s'])
                elif method in ('robust_greedy', 'robust_local'):
                    chosen, diagnostic = heuristic(graph, caps, k, budget, method == 'robust_local'); status = 'heuristic'
                else:
                    chosen = selected_snapshot; status = 'snapshot'; diagnostic = {}
                planning_s = time.perf_counter()-clock
                if not graph.roots <= chosen or retained_bytes(graph, chosen, caps, k) > budget:
                    raise RuntimeError('Root or byte-budget invariant failed')
                allowed = []
                for lost in faultscenarios:
                    cert = certificate(restricted(graph, caps, lost), chosen)
                    for version, feasible in cert['version_coverage'].items():
                        allowed.append(dict(scope=scope, policy=method, version=version, disabled=list(lost), recoverable=feasible))
                structural.extend(allowed)
                selected_hash = digest(canonical(sorted(chosen)))
                plan = dict(scope=scope, policy=method, k=k, selected=sorted(chosen), selected_sha256=selected_hash,
                    capabilities=caps, budget_bytes=budget, retained_bytes=retained_bytes(graph, chosen, caps, k),
                    compressed_retained_bytes=graph.metadata_bytes()+len(contract(caps, k))+sum(inventory[b]['gzip_bytes'] for b in chosen),
                    status=status, diagnostic=diagnostic, planning_s=planning_s,
                    allowed_structural_requests=len(allowed), allowed_structural_exact=sum(c['recoverable'] for c in allowed))
                plans.append(plan); dump(output / 'planner_records.json', plans)
                # Replay the strongest preprocessing outage, including loss of
                # membership. This stress is stronger than the allowed k=1
                # contract. Structural k=1 checks above are separate evidence.
                lost = tuple(sorted(set(caps_for(graph, 'preprocessing').values())))
                runtime_key = digest(canonical(dict(selected=sorted(chosen), disabled=list(lost))))
                if runtime_key not in store_records:
                    store = work / 'selected_stores' / runtime_key; (store / 'blobs').mkdir(parents=True)
                    (store / 'manifest.json').write_bytes(canonical(graph.manifest()))
                    for blob in chosen:
                        link_file(blobs / (blob + '.pkl'), store / 'blobs' / (blob + '.pkl'))
                    requests = []; runtime_view = restricted(Graph.read(store / 'manifest.json'), caps, lost)
                    if runtime_view.archive:
                        raise RuntimeError('Capture archive leaked into runtime')
                    membership = {p.stem for p in (store / 'blobs').glob('*.pkl')}
                    if membership != chosen:
                        raise RuntimeError('Selected disk store membership mismatch')
                    for version, target_ids in graph.targets.items():
                        expected = certificate(runtime_view, chosen)['version_coverage'][version]
                        started = time.perf_counter(); cpu = time.process_time(); ns = time.time_ns()
                        error = None; restorer = None; ok = False
                        try:
                            restorer = WitnessRestorer(runtime_view, store, replay_execute=execute)
                            values = restorer.version(version)
                            ok = all(digest(pack(v)) == graph.nodes[t].blob for v, t in zip(values, target_ids))
                            if not ok:
                                error = 'Target digest mismatch'
                        except Exception as exc:
                            error = type(exc).__name__ + ': ' + str(exc)
                        elapsed = time.perf_counter()-started; cpu_s = time.process_time()-cpu
                        expected_blocked = not expected and bool(error) and error.startswith('RestoreError:')
                        unexpected = bool((not ok and not expected_blocked) or (ok and not expected))
                        events = [] if restorer is None else restorer.trace
                        if any(e.get('producer') and caps.get(e['producer']) in lost for e in events):
                            raise RuntimeError('Disabled processing step was executed')
                        row = dict(runtime_key=runtime_key, selected_sha256=selected_hash, first_scope=scope, first_policy=method,
                             version=version, disabled=list(lost), stress='all_preprocessing_groups_disabled',
                             stress_exceeds_k1=True, expected_recoverable=expected, exact=ok,
                             expected_blocked=expected_blocked, unexpected=unexpected, error=error,
                             start_timestamp_ns=ns, end_timestamp_ns=time.time_ns(), elapsed_s=elapsed, cpu_s=cpu_s,
                             capture_archive_empty=True, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, events=events)
                        stream.write(json.dumps(row, allow_nan=False)+'\n'); stream.flush(); requests.append(row)
                        del restorer
                        if 'values' in locals():
                            del values
                        gc.collect()
                        print(json.dumps(dict(phase='stress_recovery', policy=method, scope=scope, version=version, exact=ok, expected_blocked=expected_blocked)), flush=True)
                    store_records[runtime_key] = dict(selected=sorted(chosen), selected_sha256=selected_hash,
                        disabled=list(lost), actual_requests=len(requests), exact=sum(r['exact'] for r in requests),
                        expected_blocked=sum(r['expected_blocked'] for r in requests), unexpected=sum(r['unexpected'] for r in requests),
                        elapsed_mean_s=float(np.mean([r['elapsed_s'] for r in requests])),
                        elapsed_p50_s=float(np.quantile([r['elapsed_s'] for r in requests], .5)),
                        elapsed_p90_s=float(np.quantile([r['elapsed_s'] for r in requests], .9)),
                        elapsed_p99_s=float(np.quantile([r['elapsed_s'] for r in requests], .99)),
                        cpu_total_s=sum(r['cpu_s'] for r in requests),
                        qualification='One actual request per version and unique selected store under a deliberately stronger preprocessing outage; correlated histories on one CPU host')
                    dump(output / 'runtime_store_index.json', store_records)
                measured = store_records[runtime_key]
                rows.append(dict(scope=scope, policy=method, k=k, selected_sha256=selected_hash,
                     runtime_key=runtime_key, runtime_measurements_shared=any(r['runtime_key']==runtime_key for r in rows),
                     retained_bytes=plan['retained_bytes'], gzip_retained_bytes=plan['compressed_retained_bytes'],
                     baseline_bytes=budget, gzip_baseline_bytes=graph.metadata_bytes()+len(contract(caps,k))+sum(inventory[b]['gzip_bytes'] for b in selected_snapshot),
                     saving_bytes=budget-plan['retained_bytes'], planning_s=planning_s,
                     allowed_requests=len(allowed), allowed_exact=sum(c['recoverable'] for c in allowed),
                     stress_requests=measured['actual_requests'], stress_exact=measured['exact'],
                     stress_expected_blocked=measured['expected_blocked'], stress_unexpected=measured['unexpected'],
                     stress_latency_mean_s=measured['elapsed_mean_s'], stress_latency_p50_s=measured['elapsed_p50_s'],
                     stress_latency_p90_s=measured['elapsed_p90_s'], stress_latency_p99_s=measured['elapsed_p99_s']))
                with (output / 'summary.csv').open('w') as handle:
                    writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                print(json.dumps(dict(phase='plan_complete',scope=scope,policy=method,retained_bytes=plan['retained_bytes'],saving_bytes=budget-plan['retained_bytes'])),flush=True)
    dump(output / 'allowed_scenario_certificates.json', structural)
    dvc_report = native_dvc(graph, targets, blobs, work, output)
    # Publish the small reproducible retention frontier, never gigabytes of
    # recomputable model snapshots. Every other store retains an exact index.
    frontiers = set().union(*(set(p['selected']) for p in plans if p['scope']=='preprocessing' and p['policy']=='RecoverML_exact'))
    frontier_bytes = sum(inventory[b]['bytes'] for b in frontiers)
    if frontier_bytes > 50_000_000:
        raise RuntimeError('Selected reproducible frontier exceeds Git-safe archive limit')
    with tarfile.open(output / 'selected_frontier.tar.gz', 'w:gz') as archive:
        archive.add(output / 'manifest.json', arcname='manifest.json')
        frontier_contract = output / 'preprocessing_capability_contract.json'
        frontier_contract.write_bytes(contract(caps_for(graph, 'preprocessing'), 1))
        archive.add(frontier_contract, arcname='capability_contract.json')
        for b in sorted(frontiers):
            archive.add(blobs/(b+'.pkl'),arcname='blobs/'+b+'.pkl')
    dump(output / 'store_membership.json',dict(plans=[dict(scope=p['scope'],policy=p['policy'],selected=p['selected'],selected_sha256=p['selected_sha256']) for p in plans],
         frontier_payload_bytes=frontier_bytes, frontier_selected=sorted(frontiers),
         raw_large_stores_location=str(work), raw_large_stores_tracked=False,
         frontier_archive_sha256=file_sha(output/'selected_frontier.tar.gz')))
    return dict(result_rows=len(rows), unique_runtime_stores=len(store_records),
        actual_runtime_requests=sum(r['actual_requests'] for r in store_records.values()),
        actual_runtime_exact=sum(r['exact'] for r in store_records.values()),
        actual_expected_blocked=sum(r['expected_blocked'] for r in store_records.values()),
        actual_unexpected=sum(r['unexpected'] for r in store_records.values()),
        native_dvc_files_checked=dvc_report['physical_files_checked'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--data',type=Path,default=Path('data/letter_recognition/letter-recognition.data'))
    args=parser.parse_args();protocol=json.loads(args.protocol.read_text())
    if protocol['loss_bound'] != 1 or protocol['gzip_level'] != 6 or set(protocol['methods']) != set(METHODS):
        raise RuntimeError('Runner supports precisely the frozen k=1 and gzip-6 and five-method protocol')
    args.output.mkdir(parents=True,exist_ok=False)
    args.work.mkdir(parents=True,exist_ok=False)
    data_record=obtain_data(args.data);dump(args.output/'data_acquisition.json',data_record)
    dump(args.output/'protocol.json',protocol)
    before=frozen_sources();started=time.time_ns()
    dump(args.output/'run_start.json',dict(start_timestamp_ns=started,protocol_sha256=file_sha(args.protocol),
        source_sha256=before,environment=environment(),protocol_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        purpose='Fixed unpadded useful classification history; test the requested GB goal without changing the grid to force a positive outcome'))
    with threadpool_limits(limits=1):
        graph,inventory,models=capture(protocol,args.data,args.output,args.work)
        report=evaluate(graph,inventory,protocol,args.output,args.work)
    report.update(finish_timestamp_ns=time.time_ns(),source_changed_during_run=[p for p,h in before.items() if file_sha(Path(p))!=h],
        protocol_sha256=file_sha(args.protocol),raw_trace_sha256=file_sha(args.output/'execution_traces.jsonl.gz'),
        classification_accuracy_range=[min(m['accuracy'] for m in models),max(m['accuracy'] for m in models)],
        models=len(models),unique_payloads=len(inventory),unique_payload_bytes=sum(r['bytes'] for r in inventory.values()),
        limitations=['Constructed fixed tuning history, not a random production sample',
          'The model versions reuse one dataset and split and are correlated',
          'Storage and latency are different objectives; slower recovery can accompany lower storage',
          'Broad processing loss can require all target snapshots; negative results are retained',
          'Canonical uncompressed, gzip and native pickle results are separate representations',
          'No GPU, energy, production prevalence or second-machine result is claimed'])
    dump(args.output/'report.json',report);print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    main()
