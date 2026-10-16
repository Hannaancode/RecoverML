#!/usr/bin/env python3
"""Strong native DVC replay control with actual legacy module retirement."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from threadpoolctl import threadpool_limits
import yaml

from recoverml.capability_retention import optimize, retained_bytes
from recoverml.core import Graph, canonical, digest
from recoverml.eyeai_workflow import capabilities_for


@contextmanager
def preserved_workspace(output):
    """Keep native diagnostic files after a failure instead of losing them."""
    directory = Path(tempfile.mkdtemp(prefix='recoverml-native-retina-', dir='/tmp'))
    try:
        yield directory
    except BaseException as error:
        shutil.copytree(directory, output / 'failed_workspace')
        (output / 'failure.json').write_text(json.dumps(dict(status='FAIL',
            error=type(error).__name__ + ': ' + str(error),
            diagnostic_workspace='failed_workspace',
            qualification='Failed attempts are retained and are not counted as successful native recoveries.'), indent=2) + '\n')
        raise
    finally:
        shutil.rmtree(directory)


def run(input_directory, output, capture_id='forest_s3_v16'):
    input_directory, output = Path(input_directory).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Refuse to overwrite a native DVC result')
    output.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
    graph = Graph.read(input_directory / 'captures' / capture_id / 'manifest.json')
    commands = []

    def invoke(arguments, cwd, expected=0):
        started = time.perf_counter()
        stamp = datetime.now(timezone.utc).isoformat()
        env = dict(os.environ, PYTHONPATH=str(cwd / 'source'),
                   OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        result = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True)
        receipt = dict(command=arguments, cwd=str(cwd), started_utc=stamp,
            elapsed_s=time.perf_counter() - started, returncode=result.returncode,
            stdout=result.stdout, stderr=result.stderr, expected_returncode=expected)
        commands.append(receipt)
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode != expected:
            raise RuntimeError('Native DVC control command failed: ' + str(receipt))
        return receipt

    # /tmp is deliberately outside the synchronized workspace. A deleted module
    # must not reappear from a background synchronization operation.
    with preserved_workspace(output) as temporary:
        native = Path(temporary)
        shutil.copytree(repo / 'src' / 'recoverml', native / 'source' / 'recoverml',
                        ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(repo / 'scripts' / 'retina_dvc_stage.py', native / 'stage.py')
        (native / 'graph.json').write_bytes(canonical(graph.manifest()))
        artifacts = native / 'artifacts'
        artifacts.mkdir()
        pool = input_directory / 'payload_blobs'
        for blob in graph.roots:
            raw = (pool / (blob + '.pkl')).read_bytes()
            if digest(raw) != blob:
                raise ValueError('Capture root hash mismatch')
            (artifacts / (blob + '.pkl')).write_bytes(raw)
        stages = {}
        node_stages = {}
        for index, node in enumerate(graph.nodes.values()):
            if not node.replayable:
                continue
            name = (('features_legacy' if node.params['revision'] == 'legacy_shift3' else 'features_aligned')
                    if node.op == 'retina_features' else f'{node.op}_{node.version}')
            cmd = ' '.join(map(shlex.quote, [sys.executable, 'stage.py', '--manifest', 'graph.json',
                '--node', node.id, '--workspace', 'artifacts']))
            deps = ['stage.py', 'graph.json', 'source/recoverml/eyeai_workflow.py']
            deps += ['artifacts/' + graph.nodes[dependency].blob + '.pkl' for dependency in node.deps]
            if node.op == 'retina_features':
                deps += ['source/recoverml/' + ('eyeai_legacy.py' if node.params['revision'] == 'legacy_shift3' else 'eyeai_current.py')]
                deps += ['source/recoverml/eyeai_current.py']
            stages[name] = dict(cmd=cmd, deps=sorted(set(deps)), outs=['artifacts/' + node.blob + '.pkl'])
            node_stages[node.id] = name
        (native / 'dvc.yaml').write_text(yaml.safe_dump(dict(stages=stages), sort_keys=False))
        invoke([sys.executable, '-m', 'dvc', 'init', '--no-scm', '-q'], native)
        invoke([sys.executable, '-m', 'dvc', 'config', 'cache.type', 'copy'], native)
        first = invoke([sys.executable, '-m', 'dvc', 'repro', '-q'], native)
        all_targets = {graph.nodes[target].blob for targets in graph.targets.values() for target in targets}
        first_verified = all(digest((artifacts / (blob + '.pkl')).read_bytes()) == blob for blob in all_targets)
        legacy_node = next(node for node in graph.nodes.values()
                           if node.op == 'retina_features' and node.params['revision'] == 'legacy_shift3')
        frontier = graph.roots | {legacy_node.blob}
        legacy_file = native / 'source' / 'recoverml' / 'eyeai_legacy.py'
        invoke([sys.executable, '-c', 'import recoverml.eyeai_legacy'], native)
        legacy_file.unlink()
        pycache = native / 'source' / 'recoverml' / '__pycache__'
        if pycache.exists():
            shutil.rmtree(pycache)
        invoke([sys.executable, '-c', 'import recoverml.eyeai_legacy'], native, expected=1)
        missing_before = not legacy_file.exists()
        removed_work = []
        for path in artifacts.glob('*.pkl'):
            if path.stem not in frontier:
                removed_work.append(path.stem)
                path.unlink()
        removed_cache = []
        cache = native / '.dvc' / 'cache'
        for path in cache.rglob('*'):
            if path.is_file() and 'runs' not in path.parts:
                sha = digest(path.read_bytes())
                if sha not in frontier:
                    removed_cache.append(dict(path=str(path.relative_to(native)), sha256=sha,
                                              bytes=path.stat().st_size))
                    path.unlink()
        run_cache = cache / 'runs'
        removed_run_files = sum(path.is_file() for path in run_cache.rglob('*')) if run_cache.exists() else 0
        if run_cache.exists():
            shutil.rmtree(run_cache)
        before_cached_files = [path for path in cache.rglob('*') if path.is_file()]
        before_cached = [digest(path.read_bytes()) for path in before_cached_files]
        if not set(before_cached) <= frontier:
            raise RuntimeError('Hidden downstream output remained in DVC cache')
        invoke([sys.executable, '-m', 'dvc', 'freeze', 'features_legacy'], native)
        if legacy_file.exists():
            raise RuntimeError('Retired module unexpectedly reappeared before DVC replay')
        # Forcing a frozen stage makes DVC validate its retired source dependency.
        # Normal repro skips that unchanged retained frontier and executes every
        # missing downstream stage; disable the run cache explicitly.
        second = invoke([sys.executable, '-m', 'dvc', 'repro', '--no-run-cache', '--verbose'], native)
        missing_after = not legacy_file.exists()
        if not missing_before or not missing_after:
            raise RuntimeError('Physical retirement control is invalid because the module reappeared')
        invoke([sys.executable, '-c', 'import recoverml.eyeai_legacy'], native, expected=1)
        second_hashes = {blob: digest((artifacts / (blob + '.pkl')).read_bytes()) for blob in all_targets}
        caps, k = capabilities_for(graph, 'legacy_removed')
        with threadpool_limits(limits=1):
            selected, status, diagnostics = optimize(graph, caps, k, time_limit_s=30.)
        if status != 'ok':
            raise RuntimeError('RecoverML exact comparison was not certified')
        report = dict(status='PASS' if first_verified and all(key == value for key, value in second_hashes.items()) else 'FAIL',
            capture_id=capture_id, versions=len(graph.targets), stages=len(stages),
            first_native_repro_s=first['elapsed_s'], second_native_repro_s=second['elapsed_s'],
            actual_native_repro_commands=2, exact_unique_targets=len(second_hashes),
            expected_unique_targets=len(all_targets), native_first_exact=first_verified,
            legacy_module_absent_before=missing_before, legacy_module_absent_after=missing_after,
            isolated_temporary_directory=str(native),
            removed_cached_outputs=removed_cache, removed_workspace_outputs=removed_work,
            removed_run_cache_files=removed_run_files,
            retained_native_cache_files=len(before_cached_files), retained_native_cache_sha256=before_cached,
            native_retained_payload_bytes=sum(path.stat().st_size for path in before_cached_files),
            manual_frontier_common_bytes=retained_bytes(graph, frontier, caps, k),
            RecoverML_certified_common_bytes=retained_bytes(graph, selected, caps, k),
            manual_DVC_matches_exact_minimum=retained_bytes(graph, frontier, caps, k) == retained_bytes(graph, selected, caps, k),
            exact_solver=diagnostics, target_sha256=second_hashes,
            qualification='Native DVC can replay from a manually chosen retained feature frontier. Timing includes native stage process startup and is not a proof of algorithmic speed superiority.')
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        for path in ['dvc.yaml', 'dvc.lock', 'graph.json']:
            shutil.copy2(native / path, output / path)
        print(json.dumps({key: value for key, value in report.items() if key not in
            ('exact_solver', 'removed_cached_outputs', 'removed_workspace_outputs', 'target_sha256', 'retained_native_cache_sha256')}, indent=2))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--capture', default='forest_s3_v16')
    args = parser.parse_args()
    run(args.input, args.output, args.capture)
