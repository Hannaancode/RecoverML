"""Analytic large-universe capability-loss controls with real byte execution.

Generated providers are availability labels on local replay implementations,
not actual remote services. All groups participate in protected derivations.
Each target has direct mandatory-root producers and a self-alias identity.
Targets with at most k distinct producer groups must be stored; others survive
any k losses. This gives an independent analytic minimum for the whole family.
"""
import argparse
import itertools
import json
import math
import time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from .core import Graph,digest,pack,write_store
from .operators import execute
from .capability_retention import optimize,contract,retained_bytes,CapabilityRestorer


def build(groups,k,width=16,seed=731):
    if groups<k+1 or width<4: raise ValueError('Insufficient groups or targets')
    rng=np.random.default_rng(seed);graph=Graph();caps={};providers={};values={}
    x=np.ascontiguousarray(rng.normal(size=(32,8)))
    root=graph.add('input',[],{},x,False,'source',0.,0,mandatory=True)
    targets=[];weak_count=width//4
    for i in range(width):
        params=dict(scale=1.+(i+1)/16.,offset=(i+1)/32.)
        value=execute('affine_features',[x],params);values[i]=value
        target=graph.add('external_features',[root],{'i':i},value,False,'external',.01,i%3)
        targets.append(target)
        graph.add('affine_features',[target],dict(scale=1.,offset=0.),value,True,'self_alias',.01,i%3)
        number=k if i<weak_count else k+1
        chosen={(i*(k+1)+j)%groups for j in range(number)}
        providers[i]=chosen
    # Make every declared group relevant by assigning missing groups to strong
    # targets. This does not alter which weak targets have <=k providers.
    used=set().union(*providers.values())
    for pos,group in enumerate(sorted(set(range(groups))-used)):
        providers[weak_count+pos%(width-weak_count)].add(group)
    for i,group_set in providers.items():
        for group in sorted(group_set):
            params=dict(scale=1.+(i+1)/16.,offset=(i+1)/32.,provider=group)
            started=time.perf_counter();value=execute('affine_features',[x],params)
            if pack(value)!=pack(values[i]): raise RuntimeError('Producer bytes differ')
            nid=graph.add('affine_features',[root],params,value,True,'provider'+str(group),
                          time.perf_counter()-started,i%3)
            caps[nid]='provider'+str(group)
    graph.targets={str(v):targets[v::3] for v in range(3)}
    forced={graph.nodes[targets[i]].blob for i,p in providers.items() if len(p)<=k}
    optimum=retained_bytes(graph,graph.roots|forced,caps,k)
    weak_faults=[tuple('provider'+str(group) for group in sorted(providers[i])) for i in range(weak_count)]
    return graph,caps,optimum,weak_faults


def run(destination):
    destination.mkdir(parents=True,exist_ok=False)
    rows,traces=[],[]
    with threadpool_limits(limits=1):
        for count in (16,48,96):
            for k in (2,3):
                graph,caps,expected,weak_faults=build(count,k)
                started=time.perf_counter();selected,status,diag=optimize(graph,caps,k,time_limit_s=30.)
                elapsed=time.perf_counter()-started
                if status!='ok' or not diag['robust_certified'] or not diag['storage_optimal']:
                    raise RuntimeError('Unproved scaling store')
                if retained_bytes(graph,selected,caps,k)!=expected:
                    raise RuntimeError('Analytic robust optimum mismatch')
                case=f'groups{count:03d}-k{k}';store=destination/'stores'/case
                write_store(graph,selected,store);(store/'capability_contract.json').write_bytes(contract(caps,k))
                disk=Graph.read(store/'manifest.json')
                probes=[tuple(),*weak_faults,tuple(sorted(set(caps.values()))[:k])]
                for disabled in dict.fromkeys(probes):
                    for version,targets in graph.targets.items():
                        restorer=CapabilityRestorer(disk,store,caps,disabled);start=time.time_ns()
                        values=restorer.version(version)
                        if not all(pack(v)==graph.archive[graph.nodes[t].blob] for t,v in zip(targets,values)):
                            raise RuntimeError('Scaling hash mismatch')
                        traces.append(dict(case=case,version=version,disabled=list(disabled),
                            start_timestamp_ns=start,end_timestamp_ns=time.time_ns(),exact=True,
                            target_count=len(targets),events=restorer.trace))
                fault_universe=sum(math.comb(count,i) for i in range(k+1))
                rows.append(dict(case=case,groups=count,k=k,nodes=len(graph.nodes),physical_blobs=len(graph.candidates),
                    possible_fault_scenarios=fault_universe,oracle_calls=len(diag['iterations']),
                    master_variables=diag['master_storage_variables'],cuts=diag['cuts'],planning_s=elapsed,
                    analytic_optimum_bytes=expected,analytic_match=True,certificate=diag))
    (destination/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    (destination/'execution_traces.json').write_text(json.dumps(traces,indent=2)+'\n')
    report=dict(cases=len(rows),exact_version_probes=len(traces),
        exact_target_probes=sum(r['target_count'] for r in traces),
        largest_fault_universe=max(r['possible_fault_scenarios'] for r in rows),
        largest_oracle_calls=max(r['oracle_calls'] for r in rows),
        source_sha256=digest(Path(__file__).read_bytes()),
        planner_sha256=digest(Path(__file__).with_name('capability_retention.py').read_bytes()),
        qualification='Generated labeled-provider controls; exhaustive analytic bound and symbolic certification plus selected disk probes; not every large-universe scenario executed')
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.output),indent=2))
