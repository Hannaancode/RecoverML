"""Exact small-instance feasibility/latency comparisons, distinct from ML timings."""
import time
import numpy as np
from threadpoolctl import threadpool_limits
from .core import Graph, canonical
from .operators import execute
from .policies import exact, select
from .benchmark import write_csv


def fixture(rows, scope, seed):
    g=Graph()
    rng=np.random.default_rng(seed)
    raw=rng.normal(size=(rows,3))
    root=g.add('input',[],{},raw,False,'source',0.0,0,True)
    split_params={'rows':rows,'seed':seed}
    start=time.perf_counter(); sv=execute('split',[],split_params); elapsed=time.perf_counter()-start
    split=g.add('split',[],split_params,sv,True,'membership',elapsed,0)
    for v in range(2):
        start=time.perf_counter(); enriched=raw+rng.normal(0,.1,raw.shape); elapsed=time.perf_counter()-start
        external=g.add('external_features',[root],{'version':v},enriched,False,'unknown',elapsed,v)
        start=time.perf_counter(); fv=execute('fit_scaler',[enriched,sv],{});elapsed=time.perf_counter()-start
        fit=g.add('fit_scaler',[external,split],{},fv,True,'fitted-global',elapsed,v)
        start=time.perf_counter(); scaled_v=execute('scale',[enriched,fv],{});elapsed=time.perf_counter()-start
        scaled=g.add('scale',[external,fit],{},scaled_v,True,'row-local',elapsed,v)
        g.targets[str(v)]={'fit':[fit],'scaled':[scaled],'both':[fit,scaled]}[scope]
    return g


def run_oracle(out, policies=('recoverability',)):
    records=[]
    details=[]
    with threadpool_limits(limits=1):
        for rows in (16,64,256):
            for scope in ('fit','scaled','both'):
                for seed in (21,22):
                    g=fixture(rows,scope,seed)
                    minimum=exact(g)
                    full=g.size(g.candidates)
                    for budget in sorted({minimum['objective']-1,minimum['objective'],
                                          int((minimum['objective']+full)/2),full}):
                        oracle=exact(g,budget)
                        for policy in policies:
                            selected=select(g,policy,budget)
                            accepted=selected.status=='ok' and g.coverage(selected.retained)[0]
                            estimated=g.estimate(selected.retained) if accepted else None
                            gap=(estimated/oracle['objective']-1) if accepted and oracle['objective'] else None
                            records.append(dict(rows=rows,scope=scope,seed=seed,budget_bytes=budget,
                                policy=policy,minimum_feasible_bytes=minimum['objective'],full_bytes=full,
                                exact_feasible=oracle['feasible'],planner_accepted=accepted,
                                planner_status=selected.status,planner_bytes=g.size(selected.retained),
                                exact_estimated_s=oracle['objective'] if oracle['feasible'] else '',
                                planner_estimated_s=estimated if accepted else '',
                                relative_objective_gap=gap if gap is not None else '',
                                subsets_tested=oracle['subsets_tested']))
                    details.append(dict(rows=rows,scope=scope,seed=seed,
                                        manifest=g.manifest(),minimum=minimum))
    write_csv(out/'oracle_comparison.csv',records)
    (out/'oracle_fixtures.json').write_bytes(canonical(details))
    return records
