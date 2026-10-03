"""Audit per-request trace counts and explicitly re-execute incomplete exports.

Repairs preserve original measurements and reuse the original captured artifacts.
They never synthesize timings or silently replace benchmark data.
"""
import csv,json,time,gc,shutil
from collections import Counter
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,DiskRestorer,RestoreError,write_store
from .policies import select
from .benchmark import write_csv


def audit(p,repair=False):
    rows=list(csv.DictReader((p/'raw_requests.csv').open()))
    plans=[json.loads(l) for l in (p/'retention_plans.jsonl').open()]
    traces=[json.loads(l) for l in (p/'execution_traces.jsonl').open()]
    config=json.loads((p/'config.json').read_text())
    expected={(f'case{ci:02d}-rep{rep}',policy,str(budget),str(version))
        for ci in range(len(config['cases'])) for rep in range(config['repeats'])
        for policy in config['policies'] for budget in config['budget_fractions']
        for version in range(config['versions'])}
    observed={(r['case_id'],r['policy'],r['budget_fraction'],r['version']) for r in rows}
    if observed!=expected or len(rows)!=len(expected):
        raise ValueError('Request matrix is incomplete or has duplicate/undeclared requests')
    counts=Counter((t['case_id'],t['policy'],str(t['budget_fraction']),str(t['version']),t['action']) for t in traces if t['event']=='restore')
    existing={(v['case_id'],v['policy'],str(v['budget_fraction'])) for v in plans}
    if existing!={key[:3] for key in expected}:
        if not repair:
            raise ValueError('Selection matrix is incomplete or has undeclared selections')
    bad=set()
    for r in rows:
        key=(r['case_id'],r['policy'],r['budget_fraction'],r['version'])
        if (counts[key+('load',)]!=int(r['load_nodes']) or
            counts[key+('replay',)]!=int(r['replay_nodes']) or key[:3] not in existing):bad.add(key[:3])
    if not bad:
        assert len(plans)==len(existing)
        result=dict(requests=len(rows),selections=len(plans),histories=len({r['case_id'] for r in rows}),
                    trace_events=len(traces),unique_requests=len(rows)==len({(r['case_id'],r['policy'],r['budget_fraction'],r['version']) for r in rows}),restoration_trace_counts_match=True)
        result['declared_request_matrix_complete']=True
        (p/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    if not repair:raise ValueError(f'{len(bad)} selections have incomplete export records')
    backup=p/'before_trace_repair_requests.csv'
    if not backup.exists():shutil.copyfile(p/'raw_requests.csv',backup)
    plans=[v for v in plans if (v['case_id'],v['policy'],str(v['budget_fraction'])) not in bad]
    traces=[v for v in traces if v['event']!='restore' or (v['case_id'],v['policy'],str(v['budget_fraction'])) not in bad]
    count=0
    with threadpool_limits(limits=1):
        for caseid,policy,fraction_string in sorted(bad):
            archive=p/'capture_archives'/caseid;g=Graph.read(archive/'manifest.json')
            batch=[r for r in rows if (r['case_id'],r['policy'],r['budget_fraction'])==(caseid,policy,fraction_string)]
            budget=int(batch[0]['budget_bytes']);selection=select(g,policy,budget)
            ok=selection.status=='ok' and g.size(selection.retained)<=budget
            cov=g.coverage(selection.retained)[1]
            fraction=float(fraction_string)
            plans.append(dict(case_id=caseid,policy=policy,budget_fraction=fraction,budget_bytes=budget,
                status=selection.status,retained=sorted(selection.retained),planning_s=selection.planning_s,
                eviction_trace=selection.history,certificate=g.certificate(selection.retained),phase='trace_repair_reexecution'))
            store=p/'repair_stores'/f'{caseid}-{policy}-{fraction_string}'
            if ok:
                g.archive={b:(archive/'blobs'/(b+'.pkl')).read_bytes() for b in selection.retained}
                write_store(g,selection.retained,store);rg=Graph.read(store/'manifest.json')
            for r in batch:
                count+=1
                r.update(planning_s=selection.planning_s,retained_bytes=g.size(selection.retained),
                    structurally_recoverable=cov[r['version']],within_budget=ok)
                if not ok:
                    r.update(status=selection.status,exact=False,restore_s='',replay_nodes=0,load_nodes=0,error='not executed: budget/selection failure');continue
                gc.collect();restorer=DiskRestorer(rg,store);start=time.perf_counter()
                try:restorer.version(r['version']);status,success,error='ok',True,''
                except (RestoreError,ValueError) as exc:status,success,error='restore_failed',False,str(exc)
                elapsed=time.perf_counter()-start
                r.update(status=status,exact=success,error=error,restore_s=elapsed,
                    replay_nodes=sum(t['action']=='replay' for t in restorer.trace),
                    load_nodes=sum(t['action']=='load' for t in restorer.trace))
                for t in restorer.trace:traces.append(dict(event='restore',case_id=caseid,policy=policy,
                    budget_fraction=fraction,version=int(r['version']),phase='trace_repair_reexecution',**t))
            if ok:shutil.rmtree(store)
    write_csv(p/'raw_requests.csv',rows)
    (p/'execution_traces.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in traces))
    (p/'retention_plans.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in plans))
    metadata=p/'trace_repairs.json'
    info=json.loads(metadata.read_text()) if metadata.exists() else {'requests_reexecuted':0}
    info['requests_reexecuted']+=count
    info['original_capture_artifacts_reused']=True
    info.setdefault('additional_selections',[]).extend([list(k) for k in sorted(bad)])
    metadata.write_text(json.dumps(info,indent=2))
    result=audit(p);(p/'audit.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--repair',action='store_true')
    args=parser.parse_args();print(json.dumps(audit(args.directory,args.repair),indent=2))
