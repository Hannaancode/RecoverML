"""Disk-backed repeated benchmark. Failed/infeasible requests remain in logs."""
import csv
import gc
import json
import random
import shutil
import time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph, DiskRestorer, RestoreError, canonical, write_store, digest
from .policies import select
from .workloads import build_history


def write_csv(path, records):
    if not records:
        return
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for record in records for k in record)))
        w.writeheader()
        w.writerows(records)


class AppendLog:
    """Memory-backed journal with atomic checkpoint and complete final export."""
    def __init__(self,path,mode):
        self.path=path
        self.records=path.read_text().splitlines(keepends=True) if mode=='a' else []
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.checkpoint()
    def write(self,text):
        self.records.append(text)
    def checkpoint(self):
        temporary=self.path.with_suffix(self.path.suffix+'.tmp')
        temporary.write_text(''.join(self.records))
        temporary.replace(self.path)


def run(config_path: Path, out: Path, keep_stores=False, resume=False):
    config = json.loads(config_path.read_text())
    if resume:
        if json.loads((out/'config.json').read_text()) != config:
            raise ValueError('Resume config differs from recorded config')
        if (out/'RUN_COMPLETE').exists():
            raise ValueError('Run already complete')
        summary=list(csv.DictReader((out/'raw_requests.csv').open()))
    else:
        out.mkdir(parents=True, exist_ok=False)
        (out/'config.json').write_bytes(canonical(config))
        summary=[]
    captures = []
    cases = []
    mode='a' if resume else 'w'
    with AppendLog(out/'execution_traces.jsonl',mode) as traces, \
         AppendLog(out/'retention_plans.jsonl',mode) as plans, threadpool_limits(limits=1):
        for ci, case in enumerate(config['cases']):
            for repeat in range(config['repeats']):
                settings = dict(case, versions=config['versions'])
                seed = 100 + repeat
                case_id = f'case{ci:02d}-rep{repeat}'
                archive_dir = out/'capture_archives'/case_id
                previous=[r for r in summary if r['case_id']==case_id]
                expected=config['versions']*len(config['policies'])*len(config['budget_fractions'])
                if previous and len(previous)!=expected:
                    raise ValueError('Partial history checkpoint: start a new output directory')
                if previous:
                    g=Graph.read(archive_dir/'manifest.json')
                    from .core import environment
                    if g.env!=environment():
                        raise RestoreError('Cannot resume under a changed execution environment')
                    capture=json.loads((archive_dir/'capture_info.json').read_text())
                else:
                    g, capture = build_history(settings, seed)
                captures.append(dict(case_id=case_id, **settings, repeat=repeat,
                                     capture_total_s=capture['capture_total_s'],
                                     operator_total_s=capture['operator_total_s'],
                                     lineage_serialization_s=capture['lineage_serialization_s'],
                                     instrumentation_upper_bound_s=capture['metadata_and_serialization_s'],
                                     nodes=len(g.nodes), unique_blobs=len(g.candidates),
                                     metadata_bytes=g.metadata_bytes(), full_bytes=g.size(g.candidates),
                                     required_input_bytes=g.size(g.roots)))
                if previous:
                    cases.append(dict(case_id=case_id,settings=settings,seed=seed,
                        manifest_sha256=digest((archive_dir/'manifest.json').read_bytes())))
                    print(f'{case_id}: resumed completed history',flush=True)
                    continue
                for record in g.capture_trace:
                    traces.write(json.dumps(dict(event='capture',case_id=case_id,**record))+'\n')
                archive_dir = out/'capture_archives'/case_id
                write_store(g, g.candidates, archive_dir)
                (archive_dir/'capture_info.json').write_bytes(canonical(capture))
                cases.append(dict(case_id=case_id, settings=settings, seed=seed,
                                  manifest_sha256=digest((archive_dir/'manifest.json').read_bytes())))
                full = g.size(g.candidates)
                jobs = [(b,p) for b in config['budget_fractions'] for p in config['policies']]
                random.Random(seed+ci).shuffle(jobs)
                for fraction, policy in jobs:
                    budget = int(full*fraction)
                    selection = select(g, policy, budget)
                    retained = selection.retained
                    structural_ok, cov = g.coverage(retained)
                    plans.write(json.dumps(dict(case_id=case_id, policy=policy,
                         budget_fraction=fraction, budget_bytes=budget,
                         status=selection.status, retained=sorted(retained),
                         planning_s=selection.planning_s, eviction_trace=selection.history,
                         certificate=g.certificate(retained)))+'\n')
                    store = out/'policy_stores'/f'{case_id}-{policy}-{fraction}'
                    # Do not materialize over-budget policies; there is no execution to time.
                    in_budget = g.size(retained) <= budget and selection.status == 'ok'
                    if in_budget:
                        write_store(g,retained,store)
                        actual = (store/'manifest.json').stat().st_size + sum(
                            f.stat().st_size for f in (store/'blobs').iterdir())
                        assert actual == g.size(retained)
                        # Restore graph has no archive. Fresh graph/state for each request.
                        replay_graph = Graph.read(store/'manifest.json')
                    for version in range(config['versions']):
                        base = dict(case_id=case_id, dataset=settings['dataset'], rows=capture['rows'],
                          model=settings['model'], change=settings['change'], boundary=settings['boundary'],
                          protect_intermediate=settings.get('protect_intermediate',False),
                          branches=settings.get('branches',1),
                          target_scope=settings.get('target_scope','model_and_predictions'),
                          repeat=repeat, version=version, policy=policy, budget_fraction=fraction,
                          budget_bytes=budget, retained_bytes=g.size(retained), full_bytes=full,
                          metadata_bytes=g.metadata_bytes(), planning_s=selection.planning_s,
                          structurally_recoverable=cov[str(version)], within_budget=in_budget)
                        if not in_budget:
                            summary.append(dict(**base,status=selection.status, exact=False,
                                                restore_s='',replay_nodes=0,load_nodes=0,error='not executed: budget/selection failure'))
                            continue
                        gc.collect()
                        restorer = DiskRestorer(replay_graph,store)
                        start = time.perf_counter()
                        try:
                            restorer.version(str(version))
                            elapsed = time.perf_counter()-start
                            status, success, error = 'ok',True,''
                        except (RestoreError,ValueError) as exc:
                            elapsed = time.perf_counter()-start
                            status, success, error = 'restore_failed',False,str(exc)
                        summary.append(dict(**base,status=status,exact=success,restore_s=elapsed,
                            replay_nodes=sum(t['action']=='replay' for t in restorer.trace),
                            load_nodes=sum(t['action']=='load' for t in restorer.trace),error=error))
                        for t in restorer.trace:
                            traces.write(json.dumps(dict(event='restore',case_id=case_id,policy=policy,
                                budget_fraction=fraction,version=version,**t))+'\n')
                    if in_budget and not keep_stores:
                        shutil.rmtree(store)
                # Checkpoint raw CSVs after every history, so long runs can be resumed analytically.
                traces.checkpoint()
                plans.checkpoint()
                write_csv(out/'raw_requests.csv',summary)
                write_csv(out/'capture_metrics.csv',captures)
                print(f'{case_id}: {case["dataset"]} {case["model"]} {case["boundary"]} {len(g.nodes)} nodes',flush=True)
        (out/'environment.json').write_bytes(canonical(g.env))
    (out/'histories.json').write_bytes(canonical(cases))
    (out/'RUN_COMPLETE').write_text('All requested histories, budgets, policies and versions executed.\n')
    return summary
