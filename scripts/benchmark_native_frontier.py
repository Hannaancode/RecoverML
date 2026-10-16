"""Fixed paired CLI recovery comparison with an efficient native DVC batch."""
import argparse
import csv
import itertools
import json
import os
from pathlib import Path
import random
import resource
import shlex
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

from threadpoolctl import threadpool_limits
import yaml
from recoverml.capability_retention import contract, retained_bytes
from recoverml.core import canonical, digest, write_store
from recoverml.dag_retention import optimize
from recoverml.multiview_workflow import capture


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'scripts/native_frontier_worker.py'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(output, protocol, seed):
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads(protocol.read_bytes())
    if seed not in config['seeds']:
        raise ValueError('Seed is outside frozen protocol')
    (output / 'protocol.json').write_bytes(protocol.read_bytes())
    sources = sorted((ROOT / 'src/recoverml').glob('*.py')) + [Path(__file__).resolve(), WORKER, protocol.resolve()]
    hashes = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sources}
    dump(output / 'run_start.json', dict(timestamp_ns=time.time_ns(), seed=seed, source_sha256=hashes,
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()))
    with tarfile.open(output / 'source_snapshot.tar.gz', 'w:gz') as archive:
        for path in sources:
            archive.add(path, arcname=path.relative_to(ROOT))
    rows = []
    command_log = []
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', DVC_NO_ANALYTICS='true')

    def invoke(arguments, cwd, label):
        clock, cpu = time.perf_counter(), resource.getrusage(resource.RUSAGE_CHILDREN)
        result = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt = dict(label=label, command=arguments, cwd=str(cwd), returncode=result.returncode,
            elapsed_s=time.perf_counter()-clock, cpu_s=(after.ru_utime+after.ru_stime)-(cpu.ru_utime+cpu.ru_stime),
            stdout=result.stdout, stderr=result.stderr)
        command_log.append(receipt)
        dump(output / 'commands.json', command_log)
        if result.returncode:
            raise RuntimeError('Native command failed; see commands.json: ' + label)
        return receipt

    with threadpool_limits(limits=1):
        for dataset, versions, concat in itertools.product(config['datasets'], config['versions'], config['concat_materialized']):
            history = f'{dataset}-s{seed}-v{versions}-concat{int(concat)}'
            case = output / 'cases' / history
            case.mkdir(parents=True)
            graph, info = capture(dataset, seed, versions, concat)
            caps = {n.id: 'shared_standardization_entrypoint' for n in graph.nodes.values() if n.op == 'view_standardize'}
            selected, status, diagnostic = optimize(graph, caps, 1)
            if status != 'ok':
                raise RuntimeError('Uncertified native comparison retention')
            targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
            write_store(graph, graph.candidates, output / 'captures' / history)
            dump(case / 'capture_info.json', info)
            dump(case / 'retention.json', dict(selected=sorted(selected), common_bytes=retained_bytes(graph, selected, caps, 1),
                proof=diagnostic['proof'], target_sha256=sorted(targets), failure_contract=json.loads(contract(caps, 1))))
            with tempfile.TemporaryDirectory(prefix='recoverml-native-paired-') as temporary:
                base = Path(temporary)
                workspaces = {method: base / method for method in config['methods']}
                for workspace in workspaces.values():
                    write_store(graph, selected, workspace)
                    (workspace / 'capability_contract.json').write_bytes(contract(caps, 1))
                    (workspace / 'outputs').mkdir()
                native = workspaces['DVC_native_batch']
                downstream = sorted(targets - selected)
                # Snapshot-selected targets are already persistent and need no recomputation.
                # All downstream computation is batched into ONE native DVC stage.
                stages = {}
                selected_features = sorted(selected - graph.roots - targets)
                for index, blob in enumerate(selected_features):
                    stages['retained_frontier_' + str(index)] = dict(
                        cmd=shlex.join([sys.executable, str(WORKER), '--engine', 'blocked', '--workspace', '.', '--receipt', 'blocked.json']),
                        frozen=True, outs=['blobs/' + blob + '.pkl'])
                dependencies = ['manifest.json', 'capability_contract.json', str(WORKER)]
                dependencies += ['blobs/' + blob + '.pkl' for blob in sorted(selected)]
                stages['restore_all_targets'] = dict(
                    cmd=shlex.join([sys.executable, str(WORKER), '--engine', 'dvc_batch', '--workspace', '.', '--receipt', 'worker.json']),
                    deps=dependencies, outs=['outputs/' + blob + '.pkl' for blob in sorted(targets)])
                (native / 'dvc.yaml').write_text(yaml.safe_dump(dict(stages=stages), sort_keys=False))
                # Prepare an ordinary successful lock. This initialization is untimed setup.
                for blob in targets:
                    (native / 'outputs' / (blob + '.pkl')).write_bytes(graph.archive[blob])
                invoke([sys.executable, '-m', 'dvc', 'init', '--no-scm', '-q'], native, history + ':init')
                invoke([sys.executable, '-m', 'dvc', 'config', 'cache.type', 'copy'], native, history + ':cache-type')
                invoke([sys.executable, '-m', 'dvc', 'commit', '-f'], native, history + ':commit')
                for filename in ('dvc.yaml', 'dvc.lock'):
                    shutil.copy2(native / filename, case / filename)
                for repetition in range(config['repetitions']):
                    methods = list(config['methods'])
                    random.Random(history + str(repetition)).shuffle(methods)
                    for method in methods:
                        workspace = workspaces[method]
                        outputs = workspace / 'outputs'
                        for path in outputs.iterdir():
                            path.unlink()
                        for blob in targets & selected:
                            os.link(workspace / 'blobs' / (blob + '.pkl'), outputs / (blob + '.pkl'))
                        cache = workspace / '.dvc/cache'
                        if cache.exists():
                            shutil.rmtree(cache)
                        # Each process can read only the selected physical blob files in its store.
                        present = {p.stem for p in (workspace / 'blobs').glob('*.pkl')}
                        if present != selected or any(digest((workspace / 'blobs' / (b + '.pkl')).read_bytes()) != b for b in present):
                            raise RuntimeError('Native initial retained bytes differ')
                        require_no_cache = not cache.exists()
                        if method == 'DVC_native_batch':
                            command = [sys.executable, '-m', 'dvc', 'repro', '--no-run-cache', '-q']
                        else:
                            command = [sys.executable, str(WORKER), '--engine', 'recoverml', '--workspace', '.', '--receipt', 'worker.json']
                        receipt = invoke(command, workspace, history + ':' + method + ':' + str(repetition))
                        verification_started = time.perf_counter()
                        measured = {blob: digest((outputs / (blob + '.pkl')).read_bytes()) for blob in targets}
                        elapsed = receipt['elapsed_s'] + time.perf_counter() - verification_started
                        if any(blob != actual for blob, actual in measured.items()):
                            raise RuntimeError('Native recovery did not produce every exact target file')
                        # A fully retained snapshot may let DVC skip its batch worker.
                        worker_path = workspace / 'worker.json'
                        worker = json.loads(worker_path.read_bytes()) if worker_path.exists() else None
                        if worker_path.exists():
                            worker_path.unlink()
                        if worker is not None:
                            dump(case / (method + '_' + str(repetition) + '.json'), worker)
                        row = dict(history=history, dataset=dataset, seed=seed, versions=versions,
                            concat_materialized=concat, method=method, repetition=repetition,
                            timestamp_ns=time.time_ns(), elapsed_s=elapsed, subprocess_s=receipt['elapsed_s'],
                            child_cpu_s=receipt['cpu_s'], core_s=None if worker is None else worker['core_elapsed_s'],
                            exact_targets=len(measured), expected_targets=len(targets), common_bytes=retained_bytes(graph, selected, caps, 1),
                            no_downstream_cache_before=require_no_cache, initial_payloads=sorted(present), target_sha256=measured,
                            downstream_targets=len(downstream), paired_order=methods.index(method))
                        rows.append(row)
                        with (output / 'raw_recovery.jsonl').open('a') as stream:
                            stream.write(json.dumps(row, allow_nan=False) + '\n')
                print(json.dumps(dict(history=history, completed_requests=len(rows), status='PASS')), flush=True)
    with tarfile.open(output / 'captures.tar.gz', 'w:gz') as archive:
        archive.add(output / 'captures', arcname='captures')
    with tarfile.open(output / 'case_receipts.tar.gz', 'w:gz') as archive:
        archive.add(output / 'cases', arcname='cases')
    comparisons = []
    for history in sorted({r['history'] for r in rows}):
        medians = {m: statistics.median(r['elapsed_s'] for r in rows if r['history'] == history and r['method'] == m)
                   for m in config['methods']}
        comparisons.append(dict(history=history, median_s=medians,
            dvc_to_recoverml_ratio=medians['DVC_native_batch'] / medians['RecoverML_native']))
    changed = [path for path, expected in hashes.items() if digest((ROOT / path).read_bytes()) != expected]
    dump(output / 'run_end.json', dict(status='PASS' if not changed else 'FAIL', seed=seed,
        histories=len(comparisons), native_commands=len(rows), exact_target_checks=sum(r['exact_targets'] for r in rows),
        source_changed=changed, comparisons=comparisons,
        closed_evidence_sha256={p.name: digest(p.read_bytes()) for p in output.iterdir() if p.is_file()},
        qualification=config['limitations']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=Path('configs/native_frontier_latency_oct16.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args()
    run(args.output, args.protocol, args.seed)
