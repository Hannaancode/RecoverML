"""Replay every saved dual-backend request from the archived disk stores only."""
import argparse
import gzip
import json
import tarfile
import tempfile
import time
from pathlib import Path

from threadpoolctl import threadpool_limits
from recoverml.core import Graph, RestoreError, digest, pack
from recoverml.capability_retention import CapabilityRestorer
from recoverml import operators  # Load pinned numerical libraries before thread limits.


def audit(evidence, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    original = json.loads(gzip.decompress((evidence / 'execution_traces.json.gz').read_bytes()))
    rows = []
    with tempfile.TemporaryDirectory(prefix='recoverml_capability_audit_') as temporary:
        root = Path(temporary)
        with tarfile.open(evidence / 'stores.tar.gz') as archive:
            archive.extractall(root, filter='data')
        with threadpool_limits(limits=1):
            for request in original:
                store = root / 'stores' / request['case'] / request['policy']
                graph = Graph.read(store / 'manifest.json')
                if graph.archive:
                    raise RuntimeError('Unexpected capture archive')
                contract = json.loads((store / 'capability_contract.json').read_bytes())
                restorer = CapabilityRestorer(graph, store, contract['capabilities'], request['disabled'])
                started = time.time_ns()
                cpu = time.process_time()
                exact = False
                error = None
                try:
                    values = restorer.version(request['version'])
                    exact = all(digest(pack(value)) == graph.nodes[target].blob
                                for target, value in zip(graph.targets[request['version']], values))
                    if not exact:
                        raise RuntimeError('Target byte hash mismatch')
                except RestoreError as exc:
                    if not request['expected_blocked']:
                        raise
                    error = str(exc)
                if exact != request['exact'] or (error is not None) != request['expected_blocked']:
                    raise RuntimeError('Saved request outcome was not reproduced')
                if any(event.get('producer') and
                       contract['capabilities'].get(event['producer']) in request['disabled']
                       for event in restorer.trace):
                    raise RuntimeError('Disabled producer used')
                rows.append(dict(case=request['case'], policy=request['policy'],
                    version=request['version'], disabled=request['disabled'], exact=exact,
                    expected_blocked=error is not None, error=error,
                    start_timestamp_ns=started, end_timestamp_ns=time.time_ns(),
                    cpu_s=time.process_time()-cpu, events=restorer.trace,
                    capture_archive_absent=True))
    payload=(json.dumps(rows, indent=2)+'\n').encode()
    (output/'execution_traces.json.gz').write_bytes(gzip.compress(payload, mtime=0))
    report=dict(attempts=len(rows), exact=sum(row['exact'] for row in rows),
        expected_blocked=sum(row['expected_blocked'] for row in rows),
        all_outcomes_reproduced=True, capture_archive_used=False,
        source_sha256=digest(Path(__file__).read_bytes()),
        input_archive_sha256=digest((evidence/'stores.tar.gz').read_bytes()),
        raw_trace_sha256=digest(payload))
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.evidence,args.output),indent=2))
