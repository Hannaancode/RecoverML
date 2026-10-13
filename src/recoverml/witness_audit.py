"""Audit existing manifests for root-grounded alternative recovery opportunities."""
import argparse
import json
from pathlib import Path
from .core import Graph, digest
from .witness import certificate


def audit(source):
    rows = []
    for path in sorted(source.glob('*/manifest.json')):
        graph = Graph.read(path)
        witness = certificate(graph, graph.roots)
        opaque = {n.blob for n in graph.nodes.values()
                  if not n.replayable and n.blob not in graph.roots}
        rows.append(dict(case=path.parent.name,
            manifest_sha256=digest(path.read_bytes()),
            logical_root_coverage=graph.coverage(graph.roots)[1],
            witness_root_coverage=witness['version_coverage'],
            opaque_blobs=len(opaque),
            root_derivable_opaque_blobs=len(opaque & set(witness['available']))))
    if not rows:
        raise ValueError('No captured manifests found')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = audit(args.source)
    # Keep earlier audits intact rather than replacing experimental evidence.
    with args.output.open('x') as output:
        output.write(json.dumps(rows, indent=2)+'\n')
    print(json.dumps(dict(manifests=len(rows),
        root_derivable_opaque_blobs=sum(r['root_derivable_opaque_blobs'] for r in rows))))
