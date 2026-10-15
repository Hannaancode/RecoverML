#!/usr/bin/env python3
"""Ordinary native DVC stage for one recorded retinal operator."""
import argparse
from pathlib import Path

from threadpoolctl import threadpool_limits

from recoverml.core import Graph, RestoreError, digest, environment, pack, unpack
from recoverml.eyeai_workflow import execute


def run(manifest, node_id, workspace):
    graph = Graph.read(Path(manifest))
    node = graph.nodes[node_id]
    with threadpool_limits(limits=1):
        if graph.env != environment():
            raise RestoreError('Native DVC stage environment contract mismatch')
        values = []
        for dependency in node.deps:
            blob = graph.nodes[dependency].blob
            raw = (Path(workspace) / (blob + '.pkl')).read_bytes()
            if digest(raw) != blob:
                raise RestoreError('Native DVC input hash mismatch')
            values.append(unpack(raw))
        value = execute(node.op, values, node.params)
        raw = pack(value)
        if digest(raw) != node.blob:
            raise RestoreError('Native DVC replay output hash mismatch')
        (Path(workspace) / (node.blob + '.pkl')).write_bytes(raw)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--workspace', default='artifacts')
    arguments = parser.parse_args()
    run(arguments.manifest, arguments.node, arguments.workspace)
