"""Content-addressed artifacts, dependency closure, disk restoration and verification.

Guarantees are conditional on correct operator contracts, complete dependencies,
recorded parameters, matching execution environment and intact retained artifacts.
"""
from __future__ import annotations
import hashlib
import io
import json
import pickle
import platform
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def pack(value: Any) -> bytes:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    if isinstance(value,(RandomForestClassifier,LogisticRegression)):
        from .model_codec import dumps
        return dumps(value)
    return pickle.dumps(value,protocol=5)


def unpack(raw: bytes) -> Any:
    from .model_codec import PREFIX, loads
    return loads(raw) if raw.startswith(PREFIX) else pickle.loads(raw)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def environment() -> dict:
    import numpy, scipy, sklearn, threadpoolctl
    return dict(python=platform.python_version(), numpy=numpy.__version__,
                scipy=scipy.__version__, sklearn=sklearn.__version__,
                machine=platform.machine(), system=platform.system(),
                threads=threadpoolctl.threadpool_info(), serialization='pickle-protocol-5-arrays-and-canonical-model-v1',
                model_codec_sha256=digest(Path(__file__).with_name('model_codec.py').read_bytes()),
                codec_code_sha256=digest(Path(__file__).read_bytes()),
                operator_code_sha256=digest(Path(__file__).with_name('operators.py').read_bytes()))


@dataclass
class Node:
    id: str
    op: str
    deps: list[str]
    params: dict
    replayable: bool
    scope: str
    blob: str
    size: int
    compute_s: float
    version: int


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    # A capture archive is an experimental oracle, NEVER an available restore source.
    archive: dict[str, bytes] = field(default_factory=dict, repr=False)
    targets: dict[str, list[str]] = field(default_factory=dict)
    roots: set[str] = field(default_factory=set)
    capture_trace: list[dict] = field(default_factory=list, repr=False)
    env: dict = field(default_factory=environment)

    def add(self, op: str, deps: list[str], params: dict, value: Any,
            replayable: bool, scope: str, elapsed: float, version: int,
            mandatory: bool = False) -> str:
        raw = pack(value)
        bh = digest(raw)
        # Include outcome identity. Equal operation signatures with different outcomes
        # never alias. The output hash is an oracle, not a source of missing data.
        key = digest(canonical(dict(op=op, deps=deps, params=params, blob=bh,
                                    replayable=replayable, scope=scope)))
        if key not in self.nodes:
            self.nodes[key] = Node(key, op, list(deps), params, replayable, scope,
                                   bh, len(raw), elapsed, version)
        self.archive.setdefault(bh, raw)
        if mandatory:
            self.roots.add(bh)
        self.capture_trace.append(dict(version=version, node=key, op=op, blob=bh,
                                       capture_s=elapsed, bytes=len(raw)))
        return key

    @property
    def candidates(self) -> set[str]:
        return {n.blob for n in self.nodes.values()}

    def sizes(self) -> dict[str, int]:
        return {n.blob: n.size for n in self.nodes.values()}

    def manifest(self) -> dict:
        return dict(schema=1, environment=self.env,
                    nodes=[asdict(n) for n in self.nodes.values()],
                    targets=self.targets, mandatory_blobs=sorted(self.roots))

    def metadata_bytes(self) -> int:
        return len(canonical(self.manifest()))

    def size(self, retained: set[str]) -> int:
        sizes = self.sizes()
        return self.metadata_bytes() + sum(sizes[b] for b in retained)

    @classmethod
    def read(cls, path: Path) -> 'Graph':
        m = json.loads(path.read_text())
        if m['schema'] != 1:
            raise ValueError('Unsupported manifest schema')
        g = cls(env=m['environment'])
        g.nodes = {n['id']: Node(**n) for n in m['nodes']}
        g.targets = m['targets']
        g.roots = set(m['mandatory_blobs'])
        return g

    def coverage(self, retained: set[str]) -> tuple[bool, dict[str, bool]]:
        memo: dict[str, bool] = {}
        visiting: set[str] = set()
        def can(nid: str) -> bool:
            if nid in memo:
                return memo[nid]
            if nid in visiting:
                raise ValueError('Cyclic dependency graph')
            visiting.add(nid)
            n = self.nodes[nid]
            value = n.blob in retained or (n.replayable and all(can(d) for d in n.deps))
            visiting.remove(nid)
            memo[nid] = value
            return value
        versions = {v: all(can(t) for t in targets) for v, targets in self.targets.items()}
        return all(versions.values()), versions

    def estimate(self, retained: set[str], read_bytes_per_s: float = 500e6,
                 read_latency_s: float = 2e-5) -> float:
        # Fixed hardware-independent planning model. Times are capture measurements,
        # not claimed measured restore times; no oracle payload is read here.
        total = 0.0
        for targets in self.targets.values():
            visited = set()
            def visit(nid: str) -> float:
                if nid in visited:
                    return 0.0
                visited.add(nid)
                n = self.nodes[nid]
                if n.blob in retained:
                    return read_latency_s + n.size / read_bytes_per_s
                if not n.replayable:
                    return float('inf')
                return sum(visit(d) for d in n.deps) + n.compute_s
            total += sum(visit(t) for t in targets)
        return total

    def certificate(self, retained: set[str]) -> dict:
        ok, coverage = self.coverage(retained)
        plans = {}
        for version, targets in self.targets.items():
            seen = set()
            steps = []
            def walk(nid: str):
                if nid in seen:
                    return
                seen.add(nid)
                n = self.nodes[nid]
                if n.blob in retained:
                    steps.append(dict(node=nid, action='load', blob=n.blob))
                elif n.replayable:
                    for dep in n.deps:
                        walk(dep)
                    steps.append(dict(node=nid, action='replay', dependencies=n.deps))
                else:
                    steps.append(dict(node=nid, action='unavailable', reason='non-replayable output not retained'))
            for target in targets:
                walk(target)
            plans[version] = steps
        return dict(complete=ok, version_coverage=coverage, plans=plans,
                    qualification='structural certificate under declared operator/environment contracts')


class RestoreError(RuntimeError):
    pass


class DiskRestorer:
    def __init__(self, graph: Graph, store: Path, verify_environment: bool = True):
        self.graph = graph
        self.store = store
        # Thread libraries are compared after threadpool_limits has been applied.
        if verify_environment and graph.env != environment():
            raise RestoreError('Execution environment/operator code mismatch')
        self.memo = {}
        self.trace = []

    def get(self, nid: str):
        from .operators import execute
        if nid in self.memo:
            self.trace.append(dict(node=nid, action='memory_reuse', elapsed_s=0.0,
                                   verify_s=0.0, bytes=0, exact=True))
            return self.memo[nid]
        n = self.graph.nodes[nid]
        path = self.store / 'blobs' / (n.blob + '.pkl')
        start = time.perf_counter()
        if path.is_file():
            raw = path.read_bytes()
            action = 'load'
            work = time.perf_counter() - start
            verify_start = time.perf_counter()
            if len(raw) != n.size or digest(raw) != n.blob:
                raise RestoreError(f'Corrupt retained artifact: {n.blob}')
            # Trusted local files only. Never unpickle externally supplied stores.
            value = unpack(raw)
        else:
            if not n.replayable:
                raise RestoreError(f'No exact path for {n.op}: non-replayable artifact missing')
            inputs = [self.get(d) for d in n.deps]
            start = time.perf_counter()
            value = execute(n.op, inputs, n.params)
            work = time.perf_counter() - start
            verify_start = time.perf_counter()
            raw = pack(value)
            if digest(raw) != n.blob:
                raise RestoreError(f'Replay hash mismatch for {n.op}')
            action = 'replay'
        verify = time.perf_counter() - verify_start
        self.memo[nid] = value
        self.trace.append(dict(node=nid, action=action, elapsed_s=work,
                               verify_s=verify, bytes=len(raw), exact=True))
        return value

    def version(self, version: str):
        return [self.get(t) for t in self.graph.targets[version]]


def write_store(graph: Graph, retained: set[str], destination: Path):
    """Materialize a selected policy from the capture archive, outside restore timing."""
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'blobs').mkdir()
    (destination / 'manifest.json').write_bytes(canonical(graph.manifest()))
    for blob in sorted(retained):
        (destination / 'blobs' / (blob + '.pkl')).write_bytes(graph.archive[blob])


def validate_eviction(graph: Graph, current: set[str], remove: set[str], budget: int) -> set[str]:
    proposed = current - remove
    if not graph.roots <= proposed:
        raise RestoreError('Eviction would delete a required input artifact')
    if not graph.coverage(proposed)[0]:
        raise RestoreError('Eviction would break protected-target recoverability')
    if graph.size(proposed) > budget:
        raise RestoreError('Eviction does not satisfy budget')
    return proposed
