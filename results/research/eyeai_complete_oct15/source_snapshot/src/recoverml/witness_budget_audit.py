"""Independently rerun both executors from already selected witness stores.

This audit reads no capture archives and does not modify existing experiments.
Every equal-budget attempt, including expected blocked requests, has a raw
timestamped trace. Returned values are checked against manifest byte identities.
Original summary counts are compared to freshly observed outcomes.
"""
import argparse
import csv
import json
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph, DiskRestorer, RestoreError, digest, pack, environment
from .witness import WitnessRestorer


def audit(sources,destination):
    destination.mkdir(parents=True,exist_ok=False)
    rows,counts=[],[]
    # Load numerical libraries before limiting threads so newly imported pools
    # do not escape the capture-time single-thread contract.
    environment()
    with threadpool_limits(limits=1):
        for source in sources:
            summaries=list(csv.DictReader((source/'summary.csv').open()))
            for summary in summaries:
                store=source/'stores'/summary['case']/'witness'
                manifest=store/'manifest.json'
                graph=Graph.read(manifest)
                if graph.archive: raise RuntimeError('Audit must not contain capture payloads')
                retained={b for b in graph.candidates if (store/'blobs'/(b+'.pkl')).is_file()}
                structural=graph.coverage(retained)[1]
                observed={'logical':0,'witness':0}
                for version,targets in graph.targets.items():
                    for policy in ('logical','witness'):
                        started=time.time_ns(); cpu=time.process_time()
                        restorer=(DiskRestorer(graph,store) if policy=='logical' else WitnessRestorer(graph,store))
                        error=None; exact=False
                        try:
                            values=restorer.version(version)
                            exact=all(digest(pack(value))==graph.nodes[target].blob and
                                      len(pack(value))==graph.nodes[target].size
                                      for target,value in zip(targets,values))
                            if not exact: raise RuntimeError('Audit target hash mismatch')
                            observed[policy]+=1
                        except RestoreError as exc:
                            if policy=='witness' or structural[version]:
                                raise RuntimeError('Unexpected equal-budget recovery failure') from exc
                            error=str(exc)
                        rows.append(dict(experiment=source.name,case=summary['case'],version=version,
                            policy=policy,transport=summary['transport'],
                            start_timestamp_ns=started,end_timestamp_ns=time.time_ns(),
                            cpu_s=time.process_time()-cpu,exact=exact,
                            expected_blocked=error is not None,error=error,
                            manifest_sha256=digest(manifest.read_bytes()),
                            archive_absent=True,events=restorer.trace))
                expected={'logical':int(summary['baseline_at_witness_budget']),
                          'witness':int(summary['witness_at_witness_budget'])}
                if observed!=expected: raise RuntimeError('Prior outcome counts do not reproduce')
                counts.append(dict(experiment=source.name,case=summary['case'],observed=observed,
                                   prior_counts_match=True))
    (destination/'requests.json').write_text(json.dumps(rows,indent=2)+'\n')
    (destination/'cases.json').write_text(json.dumps(counts,indent=2)+'\n')
    with (destination/'requests.csv').open('w') as stream:
        fields=[k for k in rows[0] if k!='events']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({k:r[k] for k in fields} for r in rows)
    report=dict(cases=len(counts),attempts=len(rows),exact_requests=sum(r['exact'] for r in rows),
        expected_blocked=sum(r['expected_blocked'] for r in rows),
        prior_case_counts_all_reproduced=True,archive_payload_reads=0,
        source_sha256=digest(Path(__file__).read_bytes()),
        source_summaries={str(p):digest((p/'summary.csv').read_bytes()) for p in sources})
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.source,args.output),indent=2))
