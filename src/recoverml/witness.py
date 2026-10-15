"""Experimental exact artifact recovery through captured alternative producers.

This recovers an artifact value, not the original execution or its side effects.
No algebraic equivalence is inferred: only identical captured byte hashes alias.
Contracts must declare pure deterministic operators and a matching environment.
The least fixed point prevents cycles introduced by physical hash aliasing from
being mistaken for recovery paths. Existing logical recovery is unchanged.
"""
from pathlib import Path
import heapq
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
    # Index each distinct dependency blob once per producer. Only consumers
    # of newly grounded blobs need revisiting and rounds preserve the original
    # producer order and certificate exactly.
    producers = {n.id:n for n in graph.nodes.values() if n.replayable}
    consumers = {}
    remaining = {}
    ready = []
    for nid,node in producers.items():
        missing={graph.nodes[d].blob for d in node.deps}-available
        remaining[nid]=len(missing)
        for blob in missing: consumers.setdefault(blob,[]).append(nid)
        if not missing: heapq.heappush(ready,(node.compute_s,nid))
    round_number = 0
    while True:
        added = set()
        while ready:
            _,nid=heapq.heappop(ready)
            node=producers[nid]
            if node.blob in available or not node.replayable:
                continue
            dependencies = [graph.nodes[d].blob for d in node.deps]
            available.add(node.blob)
            added.add(node.blob)
            steps.append(dict(blob=node.blob, action='replay', producer=node.id,
                              dependencies=dependencies, round=round_number))
        if not added:
            break
        for blob in added:
            for nid in consumers.get(blob,[]):
                remaining[nid]-=1
                if remaining[nid]==0:
                    heapq.heappush(ready,(producers[nid].compute_s,nid))
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
    def __init__(self, graph, store: Path, verify_environment=True, *, replay_execute=None):
        # Reuse existing environment contract without using logical restoration.
        DiskRestorer(graph, store, verify_environment=verify_environment)
        self.graph, self.store = graph, store
        self.replay_execute = replay_execute
        retained = {b for b in graph.candidates if
                    (store / 'blobs' / (b + '.pkl')).is_file()}
        self.plan = {s['blob']: s for s in certificate(graph, retained)['steps']}
        self.memo, self.trace = {}, []

    def get(self, nid):
        requested = self.graph.nodes[nid]
        return self._blob(requested.blob, nid)

    def _blob(self, blob, requested_id):
        from .operators import execute
        # Execute the grounded witness in dependency order without consuming
        # Python's call stack. Only dependencies of this request are visited.
        # A postorder frame preserves the recursive executor's event order and
        # inclusive elapsed time while allowing arbitrarily deep captured DAGs.
        pending = [(blob, requested_id, False, None)]
        visiting = set()
        while pending:
            current, requested, expanded, started = pending.pop()
            if current in self.memo:
                continue
            if current not in self.plan:
                raise RestoreError('No grounded alternative producer for ' + current)
            step = self.plan[current]
            if not expanded:
                if current in visiting:
                    raise RestoreError('Cyclic alternative-producer witness: ' + current)
                started = time.perf_counter()
                if step['action'] != 'load':
                    visiting.add(current)
                    producer = self.graph.nodes[step['producer']]
                    pending.append((current, requested, True, started))
                    pending.extend((self.graph.nodes[d].blob, d, False, None)
                                   for d in reversed(producer.deps))
                    continue
            if step['action'] == 'load':
                try:
                    raw = (self.store / 'blobs' / (current + '.pkl')).read_bytes()
                except OSError as exc:
                    raise RestoreError('Cannot read retained artifact: ' + current) from exc
                if digest(raw) != current:
                    raise RestoreError('Corrupt retained artifact: ' + current)
                value = unpack(raw)
                producer = None
            else:
                producer = self.graph.nodes[step['producer']]
                inputs = [self.memo[self.graph.nodes[d].blob] for d in producer.deps]
                replay_execute = self.replay_execute or execute
                value = replay_execute(producer.op, inputs, producer.params)
                raw = pack(value)
                if len(raw) != producer.size or digest(raw) != current:
                    raise RestoreError('Alternative producer hash mismatch: ' + producer.id)
                visiting.remove(current)
            self.memo[current] = value
            self.trace.append(dict(requested_node=requested, blob=current,
                producer=None if producer is None else producer.id,
                action=step['action'], alternative=producer is not None and producer.id != requested,
                elapsed_s=time.perf_counter()-started, bytes=len(raw), exact=True,
                end_timestamp_ns=time.time_ns()))
        return self.memo[blob]

    def version(self, version):
        return [self.get(t) for t in self.graph.targets[version]]
