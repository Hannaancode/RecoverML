"""Reference exact scenario-expanded robust retention formulation.

This independently models each allowed loss scenario with load/replay choices
and continuous topological ranks. It solves the same byte objective and fault
contract as capability_retention. It is our attributed reference formulation,
not the implementation of another published system.
"""
import itertools
import math
import time
from .capability_retention import validate, contract, retained_bytes, restricted
from .witness import certificate


def optimize(graph, capabilities, k, time_limit_s=30., maximum_scenarios=2000):
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import coo_matrix
    validate(graph, capabilities, k)
    if time_limit_s <= 0 or not math.isfinite(time_limit_s):
        raise ValueError('Positive finite time limit required')
    groups=sorted(set(capabilities.values()))
    scenarios=sum(math.comb(len(groups),i) for i in range(min(k,len(groups))+1))
    if scenarios>maximum_scenarios:
        return graph.roots, 'scenario_limit', dict(storage_optimal=False,
            robust_certified=False, scenarios=scenarios, scenario_limit=maximum_scenarios)
    faults=[set(f) for i in range(min(k,len(groups))+1)
            for f in itertools.combinations(groups,i)]
    blobs=sorted(graph.candidates);n=len(blobs);index={b:i for i,b in enumerate(blobs)}
    targets={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    if not n:
        return set(), 'ok', dict(storage_optimal=True,robust_certified=True,variables=0,scenarios=scenarios)
    started=time.perf_counter();sizes=graph.sizes()
    cost=[sizes[b]/1024. for b in blobs];lo=[float(b in graph.roots) for b in blobs]
    hi=[1.]*n;integer=[1]*n;constraints=[]
    def variable(low=0.,high=1.,integral=1):
        position=len(cost);cost.append(0.);lo.append(low);hi.append(high);integer.append(integral)
        return position
    def add(terms,lower=-math.inf,upper=math.inf):
        constraints.append((terms,lower,upper))
    for lost in faults:
        available={b:variable(low=float(b in targets)) for b in blobs}
        ranks={b:variable(high=n,integral=0) for b in blobs}
        producers=[p for p in graph.nodes.values() if p.replayable and capabilities.get(p.id) not in lost]
        replay={p.id:variable() for p in producers}
        sources={b:{available[b]:1.,index[b]:-1.} for b in blobs}
        for p in producers:
            sources[p.blob][replay[p.id]]=-1.
            add({replay[p.id]:1.,available[p.blob]:-1.},upper=0.)
            for dependency in {graph.nodes[d].blob for d in p.deps}:
                add({replay[p.id]:1.,available[dependency]:-1.},upper=0.)
                terms={replay[p.id]:-float(n+1)}
                for col,value in ((ranks[p.blob],1.),(ranks[dependency],-1.)):
                    terms[col]=terms.get(col,0.)+value
                add(terms,lower=-float(n))
        for b in blobs:
            add(sources[b],upper=0.)
            add({index[b]:1.,available[b]:-1.},upper=0.)
    rr,cc,vv,ll,uu=[],[],[],[],[]
    for row,(terms,lower,upper) in enumerate(constraints):
        for col,value in terms.items():rr.append(row);cc.append(col);vv.append(value)
        ll.append(lower);uu.append(upper)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(constraints),len(cost))).tocsc()
    construction_s=time.perf_counter()-started;start_solver=time.perf_counter()
    result=milp(np.array(cost),integrality=np.array(integer),bounds=Bounds(lo,hi),
        constraints=LinearConstraint(matrix,ll,uu),
        options=dict(time_limit=time_limit_s,mip_rel_gap=0.))
    diag=dict(storage_optimal=result.status==0,robust_certified=False,scenarios=scenarios,
        variables=len(cost),constraints=len(constraints),construction_s=construction_s,
        solver_s=time.perf_counter()-start_solver,solver_status=int(result.status),
        solver_message=result.message)
    if result.x is None:return graph.roots,'no_incumbent',diag
    selected={b for b in blobs if result.x[index[b]]>.5}
    robust=graph.roots<=selected and all(certificate(restricted(graph,capabilities,f),selected)['complete'] for f in faults)
    diag.update(robust_certified=robust,retained_bytes=retained_bytes(graph,selected,capabilities,k))
    return selected,'ok' if robust and result.status==0 else 'uncertified_optimum',diag
