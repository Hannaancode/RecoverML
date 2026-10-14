"""Post-calibration validation on new provider counts, widths and capture seed."""
import argparse
import csv
import gzip
import json
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import digest
from .capability_scaling import build
from .capability_retention import optimize as ce,retained_bytes
from .scenario_retention import optimize as direct
from .robust_retention import optimize as auto,DIRECT_SCENARIO_CUTOFF


def run(destination):
    destination.mkdir(parents=True,exist_ok=False);rows=[];traces=[]
    with threadpool_limits(limits=1):
        for groups in (8,16,32):
            for width in (12,24):
                for k in (1,2):
                    graph,caps,expected,_=build(groups,k,width=width,seed=991)
                    for trial in range(3):
                        methods=[('auto',auto),('counterexample',ce),('expanded_exact',direct)]
                        methods=methods[trial:]+methods[:trial]
                        for name,solver in methods:
                            stamp=time.time_ns();start=time.perf_counter();cpu=time.process_time()
                            chosen,status,diag=solver(graph,caps,k,time_limit_s=60.)
                            elapsed=time.perf_counter()-start;used=time.process_time()-cpu
                            if status!='ok' or not diag['storage_optimal'] or retained_bytes(graph,chosen,caps,k)!=expected:raise RuntimeError('Unproved holdout result')
                            row=dict(groups=groups,width=width,k=k,trial=trial,policy=name,elapsed_s=elapsed,cpu_s=used,
                                analytic_match=True,selected_engine=diag.get('selected_engine'),retained_bytes=expected)
                            rows.append(row);traces.append(dict(**row,start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),diagnostic=diag))
                            print(json.dumps(row),flush=True)
    with (destination/'summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    raw=(json.dumps(traces,indent=2)+'\n').encode();(destination/'execution_traces.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    report=dict(planner_runs=len(rows),graph_cases=12,all_analytic_matches=True,
        cutoff=DIRECT_SCENARIO_CUTOFF,calibration='Initial groups 6/12/24 width16 study; cutoff fixed before this validation',
        validation='Groups8/16/32 widths12/24 capture seed991; same analytic family, not independent production workflows',
        trace_sha256=digest(raw),source_sha256=digest(Path(__file__).read_bytes()),
        selector_sha256=digest(Path(__file__).with_name('robust_retention.py').read_bytes()))
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.output),indent=2))
