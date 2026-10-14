"""Validate automatic engine selection on an existing captured mixed graph."""
import argparse
import gzip
import json
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,digest
from . import operators
from .robust_retention import optimize
from .capability_retention import retained_bytes


def run(source,destination):
    destination.mkdir(parents=True,exist_ok=False);rows=[]
    original=json.loads((source/'report.json').read_text())
    with threadpool_limits(limits=1):
        for k in (1,2):
            store=source/'stores'/f'k{k}'/'expanded_exact'
            graph=Graph.read(store/'manifest.json');contract=json.loads((store/'capability_contract.json').read_text())
            expected=next(r['retained_bytes'] for r in original['rows'] if r['policy']=='expanded_exact' and r['k']==k)
            for trial in range(5):
                stamp=time.time_ns();clock=time.perf_counter();cpu=time.process_time()
                selected,status,diag=optimize(graph,contract['capabilities'],k,time_limit_s=60.)
                elapsed=time.perf_counter()-clock;work=time.process_time()-cpu
                if status!='ok' or not diag['storage_optimal'] or retained_bytes(graph,selected,contract['capabilities'],k)!=expected:raise RuntimeError('Auto mixed optimum differs')
                rows.append(dict(k=k,trial=trial,elapsed_s=elapsed,cpu_s=work,retained_bytes=expected,
                    start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),capture_archive_absent=not graph.archive,
                    selected_engine=diag['selected_engine'],diagnostic=diag))
    payload=(json.dumps(rows,indent=2)+'\n').encode();(destination/'execution_traces.json.gz').write_bytes(gzip.compress(payload,mtime=0))
    report=dict(planner_runs=len(rows),all_byte_optima_match=True,trace_sha256=digest(payload),
        source_sha256=digest(Path(__file__).read_bytes()),selector_sha256=digest(Path(__file__).with_name('robust_retention.py').read_bytes()),
        input_report_sha256=digest((source/'report.json').read_bytes()),
        input_manifest_sha256=digest((source/'stores/k1/expanded_exact/manifest.json').read_bytes()))
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.source,a.output),indent=2))
