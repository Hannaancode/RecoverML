"""Independent exhaustive validation of presolve feasibility and cost projection."""
import argparse
import csv
import hashlib
import itertools
import json
import math
import time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from .core import Graph,canonical
from .optimizer import optimize


def graph(seed):
    rng=np.random.default_rng(seed);g=Graph();nodes=[]
    root=g.add('input',[],{},np.arange(8),False,'source',0.,0,True)
    nodes.append(root)
    for i in range(9):
        parents=rng.choice(nodes,size=min(len(nodes),int(rng.integers(1,3))),replace=False).tolist()
        # Deliberate physical aliases with distinct logical contracts.
        value=np.full(4*(1+i%4),i%4,dtype=np.int64)
        nid=g.add('fixture',parents,{'logical_index':i},value,
            bool(rng.random()>.35),'oracle',float(rng.choice([0.,1e-6,1e-4,.003])),i%3)
        nodes.append(nid)
    g.targets={'0':[nodes[-1],nodes[-2]],'1':[nodes[-3],nodes[-1]],
               '2':[nodes[-4],nodes[-4]]}
    return g


def reference(g,retained):
    """No calls to Graph.coverage/estimate or optimizer frontier construction."""
    total=0.
    for targets in g.targets.values():
        seen=set()
        def produce(nid):
            if nid in seen:return 0.
            seen.add(nid);n=g.nodes[nid]
            if n.blob in retained:return 2e-5+n.size/500e6
            if not n.replayable:return float('inf')
            return n.compute_s+sum(produce(p) for p in n.deps)
        total+=sum(produce(t) for t in targets)
    return total


def run(count,out):
    out.mkdir(parents=True,exist_ok=False)
    rows=[];subsets=0;projection_checks=0;start=time.perf_counter()
    with threadpool_limits(limits=1):
        for seed in range(count):
            g=graph(17000+seed);sizes=g.sizes();metadata=g.metadata_bytes()
            frontier=set();stack=[t for ts in g.targets.values() for t in ts]
            while stack:
                nid=stack.pop()
                if nid in frontier:continue
                frontier.add(nid)
                if g.nodes[nid].replayable:stack.extend(g.nodes[nid].deps)
            live=g.roots|{g.nodes[n].blob for n in frontier}
            optional=sorted(g.candidates-g.roots);records=[]
            for flags in itertools.product((False,True),repeat=len(optional)):
                kept=g.roots|{b for b,flag in zip(optional,flags) if flag}
                size=metadata+sum(sizes[b] for b in kept)
                cost=reference(g,kept);projected=reference(g,kept&live)
                if not (cost==projected or math.isclose(cost,projected,rel_tol=1e-10,abs_tol=1e-12)):
                    raise RuntimeError('Projection changed feasibility or cost')
                projection_checks+=1;records.append((size,cost));subsets+=1
            feasible=[size for size,cost in records if math.isfinite(cost)]
            minimum=min(feasible);full=g.size(g.candidates)
            budgets=sorted(set([minimum-1,minimum,minimum+1,(minimum+full)//2,full]))
            for budget in budgets:
                valid=[cost for size,cost in records if size<=budget and math.isfinite(cost)]
                oracle=min(valid) if valid else None
                for policy,prune,compact in [('v2',False,False),('v3',True,False),('v4',True,True)]:
                    began=time.perf_counter()
                    kept,status,history=optimize(g,budget,time_limit_s=5.,prune_opaque=prune,compact=compact)
                    matches=(status=='ok')==(oracle is not None)
                    if oracle is not None:
                        matches=matches and g.size(kept)<=budget and math.isclose(
                            reference(g,kept),oracle,rel_tol=1e-6,abs_tol=1e-9)
                        matches=matches and history[0]['estimated_optimal']
                    else:matches=matches and status=='proven_infeasible'
                    if not matches:raise RuntimeError(f'oracle mismatch {seed} {budget} {policy}')
                    rows.append(dict(seed=17000+seed,policy=policy,budget_bytes=budget,
                        optional_blobs=len(optional),removed_blobs=len(g.candidates-live),
                        status=status,oracle_feasible=oracle is not None,
                        oracle_cost_s=oracle,postchecked=True,
                        planning_s=time.perf_counter()-began))
            if seed%16==0:print(f'oracle graph {seed+1}/{count} passed',flush=True)
    with (out/'oracle_comparisons.csv').open('w',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report=dict(graphs=count,subsets_enumerated=subsets,projection_checks=projection_checks,
        planner_comparisons=len(rows),all_match=True,elapsed_s=time.perf_counter()-start,
        completed_utc=datetime.now(timezone.utc).isoformat(),
        qualification='Independent exhaustive cost recursion; generated small logical DAGs and physical aliases')
    (out/'summary.json').write_bytes(canonical(report))
    (out/'environment.json').write_bytes(canonical(g.env))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out/'HASHES.json').write_bytes(canonical(hashes))
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--graphs',type=int,default=128)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(run(args.graphs,args.out),indent=2))

if __name__=='__main__':main()
