"""Experimental exact artifact recovery through captured alternative producers.

This recovers an artifact value, not the original execution or its side effects.
No algebraic equivalence is inferred: only identical captured byte hashes alias.
Contracts must declare pure deterministic operators and a matching environment.
The least fixed point prevents cycles introduced by physical hash aliasing from
being mistaken for recovery paths. Existing logical recovery is unchanged.
"""
from pathlib import Path
import time
from .core import DiskRestorer, RestoreError, digest, pack, unpack


def certificate(graph, retained):
    """Return a grounded witness without reading any capture payloads.

    Under declared replay contracts, this is complete for existence of an
    alternative-producer derivation. It does not minimize execution cost.
    Every replay's dependencies were established in an earlier round, so the
    certificate is acyclic even when the blob quotient graph contains cycles.
    """
    if not set(retained) <= graph.candidates:
        raise ValueError('Unknown retained blob')
    available = set(retained)
    steps = [dict(blob=b, action='load') for b in sorted(retained)]
    producers = sorted(graph.nodes.values(), key=lambda n: (n.compute_s, n.id))
    round_number = 0
    while True:
        previous = set(available)
        added = set()
        for node in producers:
            if node.blob in available or not node.replayable:
                continue
            dependencies = [graph.nodes[d].blob for d in node.deps]
            if all(b in previous for b in dependencies):
                available.add(node.blob)
                added.add(node.blob)
                steps.append(dict(blob=node.blob, action='replay', producer=node.id,
                                  dependencies=dependencies, round=round_number))
        if not added:
            break
        round_number += 1
    coverage = {v: all(graph.nodes[t].blob in available for t in targets)
                for v, targets in graph.targets.items()}
    return dict(complete=all(coverage.values()), version_coverage=coverage,
                steps=steps, available=sorted(available),
                semantics='exact artifact bytes; original events are not reproduced')


class WitnessRestorer:
    """Execute only a target's grounded witness and verify each materialization.

    A corrupt retained file fails closed rather than being silently bypassed.
    The archive is never read. Separate instances isolate recovery requests.
    """
    def __init__(self, graph, store: Path, verify_environment=True):
        # Reuse existing environment contract without using logical restoration.
        DiskRestorer(graph, store, verify_environment=verify_environment)
        self.graph, self.store = graph, store
        retained = {b for b in graph.candidates if
                    (store / 'blobs' / (b + '.pkl')).is_file()}
        self.plan = {s['blob']: s for s in certificate(graph, retained)['steps']}
        self.memo, self.trace = {}, []

    def get(self, nid):
        requested = self.graph.nodes[nid]
        return self._blob(requested.blob, nid)

    def _blob(self, blob, requested_id):
        from .operators import execute
        if blob in self.memo:
            return self.memo[blob]
        if blob not in self.plan:
            raise RestoreError('No grounded alternative producer for ' + blob)
        step = self.plan[blob]
        started = time.perf_counter()
        if step['action'] == 'load':
            raw = (self.store / 'blobs' / (blob + '.pkl')).read_bytes()
            if digest(raw) != blob:
                raise RestoreError('Corrupt retained artifact: ' + blob)
            value = unpack(raw)
            producer = None
        else:
            producer = self.graph.nodes[step['producer']]
            inputs = [self._blob(self.graph.nodes[d].blob, d) for d in producer.deps]
            value = execute(producer.op, inputs, producer.params)
            raw = pack(value)
            if len(raw) != producer.size or digest(raw) != blob:
                raise RestoreError('Alternative producer hash mismatch: ' + producer.id)
        self.memo[blob] = value
        self.trace.append(dict(requested_node=requested_id, blob=blob,
            producer=None if producer is None else producer.id,
            action=step['action'], alternative=producer is not None and producer.id != requested_id,
            elapsed_s=time.perf_counter()-started, bytes=len(raw), exact=True,
            end_timestamp_ns=time.time_ns()))
        return value

    def version(self, version):
        return [self.get(t) for t in self.graph.targets[version]]
