"""Identical file recovery obligation through WitnessRestorer or a DVC batch.

The DVC batch uses a direct recursive executor, not RecoverML's witness planner.
Both enforce the declared shared preprocessing loss and verify exact outputs.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time

from recoverml.core import RestoreError, digest


def reset_selected_cache(cache, blobs, layout):
    """Keep native cache references to paid payloads without duplicate storage."""
    cache, blobs = Path(cache), Path(blobs)
    expected = blobs.parent.resolve() / '.dvc' / 'cache'
    if cache.resolve() != expected:
        raise ValueError('Cache must be inside this recovery workspace')
    for relative, blob in layout.items():
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts or ':' in relative or '\\' in relative:
            raise ValueError('Unsafe native cache object path')
        source = blobs / (blob + '.pkl')
        if digest(source.read_bytes()) != blob:
            raise RestoreError('Retained native cache source hash mismatch')
    if cache.exists():
        def remove_readonly(function, path, error):
            # DVC protects cache files. Windows refuses to unlink them until
            # the write bit is restored; only touch this checked workspace.
            target = Path(path)
            if not isinstance(error, PermissionError) or not target.resolve().is_relative_to(cache.resolve()):
                raise error
            target.chmod(target.stat().st_mode | stat.S_IWUSR)
            function(path)
        shutil.rmtree(cache, onexc=remove_readonly)
    for relative, blob in layout.items():
        destination = cache / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.link(blobs / (blob + '.pkl'), destination)
    return sorted(digest(p.read_bytes()) for p in cache.rglob('*') if p.is_file())


def recover(engine, workspace):
    workspace = Path(workspace)
    # Both integrations may use the same exact-file fast path. DVC can also
    # skip its worker entirely when its retained output cache is intact.
    if engine != 'blocked':
        from recoverml.file_export import export_retained_targets
        exported = export_retained_targets(workspace, workspace / 'outputs')
        if exported is not None:
            return dict(exported, engine=engine, declared_lost_groups=['shared_standardization_entrypoint'])
    from threadpoolctl import threadpool_limits
    from recoverml.capability_retention import restricted
    from recoverml.core import Graph, environment, pack, unpack
    from recoverml.multiview_workflow import execute
    from recoverml.witness import WitnessRestorer
    graph = Graph.read(workspace / 'manifest.json')
    caps = {n.id: 'shared_standardization_entrypoint' for n in graph.nodes.values()
            if n.op == 'view_standardize'}
    output = workspace / 'outputs'
    output.mkdir(exist_ok=True)
    clock = time.perf_counter()
    with threadpool_limits(limits=1):
        if graph.env != environment():
            raise RestoreError('Native comparison environment mismatch')
        if engine == 'blocked':
            raise RestoreError('Retired preprocessing entrypoint was dispatched')
        memo = {}
        operations = []

        def direct(node_id):
            node = graph.nodes[node_id]
            if node.blob in memo:
                return memo[node.blob]
            path = workspace / 'blobs' / (node.blob + '.pkl')
            loaded = path.exists()
            if loaded:
                raw = path.read_bytes()
            else:
                if node_id in caps or not node.replayable:
                    raise RestoreError('Unavailable producer or missing mandatory input')
                value = execute(node.op, [direct(d) for d in node.deps], node.params)
                raw = pack(value)
                operations.append(dict(node=node_id, op=node.op, sha256=digest(raw)))
            if digest(raw) != node.blob:
                raise RestoreError('Direct native replay hash mismatch')
            if loaded:
                value = unpack(raw)
            memo[node.blob] = value
            return value

        view = restricted(graph, caps, ('shared_standardization_entrypoint',))
        restorer = WitnessRestorer(view, workspace, replay_execute=execute) if engine == 'recoverml' else None
        for version, targets in graph.targets.items():
            paths = [output / (graph.nodes[t].blob + '.pkl') for t in targets]
            if not all(path.exists() for path in paths):
                values = restorer.version(version) if restorer is not None else [direct(t) for t in targets]
                for target, path, value in zip(targets, paths, values):
                    raw = pack(value)
                    if digest(raw) != graph.nodes[target].blob:
                        raise RestoreError('Native target hash mismatch')
                    path.write_bytes(raw)
        targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
        actual = {blob: digest((output / (blob + '.pkl')).read_bytes()) for blob in targets}
        if any(blob != measured for blob, measured in actual.items()):
            raise RestoreError('Native target files differ')
        return dict(status='PASS', engine=engine, core_elapsed_s=time.perf_counter()-clock,
                    target_sha256=actual, declared_lost_groups=['shared_standardization_entrypoint'],
                    operations=restorer.trace if restorer is not None else operations,
                    qualification='Declared capability loss; implementation file is not physically deleted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, choices=['recoverml', 'dvc_batch', 'blocked'])
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    receipt = recover(args.engine, args.workspace)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
