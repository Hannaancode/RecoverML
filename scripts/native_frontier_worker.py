"""Identical file recovery obligation through WitnessRestorer or a DVC batch.

The DVC batch uses a direct recursive executor, not RecoverML's witness planner.
Both enforce the declared shared preprocessing loss and verify exact outputs.
"""
import argparse
import json
from pathlib import Path
import time

from threadpoolctl import threadpool_limits
from recoverml.capability_retention import restricted
from recoverml.core import Graph, RestoreError, digest, environment, pack, unpack
from recoverml.multiview_workflow import execute
from recoverml.witness import WitnessRestorer


def recover(engine, workspace):
    workspace = Path(workspace)
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
            if path.exists():
                raw = path.read_bytes()
            else:
                if node_id in caps or not node.replayable:
                    raise RestoreError('Unavailable producer or missing mandatory input')
                value = execute(node.op, [direct(d) for d in node.deps], node.params)
                raw = pack(value)
                operations.append(dict(node=node_id, op=node.op, sha256=digest(raw)))
            if digest(raw) != node.blob:
                raise RestoreError('Direct native replay hash mismatch')
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
