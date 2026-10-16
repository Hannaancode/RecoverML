"""Minimum-storage alternative-producer planning with grounded dependencies.

This is a storage objective, not the latency objective of Planner V2 to V4.
Standard MILP rank constraints rule out self-supporting physical alias cycles.
All protected targets share one retained physical set. The executor constructs
its own grounded certificate, independently of the solver's chosen witnesses.
"""
import math
import time
from .witness import certificate


def optimize(graph, budget=None, time_limit_s=10., *, alternative=True):
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix
    if not math.isfinite(time_limit_s) or time_limit_s <= 0:
        raise ValueError('Time limit must be finite and positive')
    sizes, metadata = graph.sizes(), graph.metadata_bytes()
    if any(not isinstance(size, int) or size < 0 for size in sizes.values()):
        raise ValueError('Artifact sizes must be nonnegative integers')
    blobs = sorted(graph.candidates)
    if not blobs:
        valid = not any(graph.targets.values()) and (budget is None or metadata <= budget)
        return set(), 'ok' if valid else 'proven_infeasible', dict(storage_optimal=valid)
    index = {b:i for i,b in enumerate(blobs)}
    producers = [n for n in sorted(graph.nodes.values(), key=lambda n:n.id) if n.replayable]
    nblobs = len(blobs)
    replay = {n.id:nblobs+i for i,n in enumerate(producers)}
    units = blobs if alternative else sorted(graph.nodes)
    load_start = nblobs+len(producers)
    loads = ({b:index[b] for b in blobs} if alternative else
             {nid:load_start+i for i,nid in enumerate(units)})
    rank_start = load_start if alternative else load_start+len(units)
    rank = {unit:rank_start+i for i,unit in enumerate(units)}
    count = rank_start+len(units)
    cost = np.zeros(count)
    lo, hi = np.zeros(count), np.ones(count)
    integrality = np.ones(count)
    for b in blobs:
        cost[index[b]] = sizes[b]/1024.
        lo[index[b]] = float(b in graph.roots)
    for unit in units:
        hi[rank[unit]] = len(units)
        integrality[rank[unit]] = 0
    active = {unit:{loads[unit]:1.} for unit in units}
    for n in producers:
        active[n.blob if alternative else n.id][replay[n.id]] = 1.
    rows, cols, values, lower, upper = [], [], [], [], []
    def add(terms, low=-np.inf, high=np.inf):
        row = len(lower)
        for col, value in terms.items():
            rows.append(row); cols.append(col); values.append(value)
        lower.append(low); upper.append(high)
    targets = {graph.nodes[t].blob if alternative else t
               for ts in graph.targets.values() for t in ts}
    for unit in units:
        # A blob is loaded or produced at most once in the witness DAG.
        # A selected retained blob therefore cannot use a replay producer.
        add(active[unit], low=float(unit in targets), high=1.)
        if not alternative:
            add({loads[unit]:1.,index[graph.nodes[unit].blob]:-1.},high=0.)
    if budget is not None:
        add({index[b]:sizes[b]/1024. for b in blobs}, high=(budget-metadata)/1024.)
    big_m = len(units)+1
    for n in producers:
        r = replay[n.id]
        output = n.blob if alternative else n.id
        if not alternative:
            add({r:1.,index[n.blob]:1.},high=1.)
        for parent in set(graph.nodes[d].blob if alternative else d for d in n.deps):
            terms = {r:1.}
            for col, value in active[parent].items():
                terms[col] = terms.get(col,0.)-value
            add(terms, high=0.)
            # Use accumulation because equal input/output hashes share a rank.
            terms = {r:-float(big_m)}
            for col, value in [(rank[output],1.), (rank[parent],-1.)]:
                terms[col] = terms.get(col,0.)+value
            add(terms, low=1-big_m)
    matrix = coo_matrix((values,(rows,cols)),shape=(len(lower),count)).tocsc()
    started = time.perf_counter()
    result = milp(cost, integrality=integrality, bounds=Bounds(lo,hi),
        constraints=LinearConstraint(matrix,lower,upper),
        options={'time_limit':time_limit_s,'mip_rel_gap':0.})
    diagnostic = dict(solver_status=int(result.status), solver_message=result.message,
        solver_s=time.perf_counter()-started, variables=count, constraints=len(lower),
        physical_blobs=nblobs, producers=len(producers), alternative_producers=alternative,
        storage_optimal=result.status==0,
        objective='retained physical bytes including fixed manifest',
        mip_gap=float(result.mip_gap) if getattr(result,'mip_gap',None) is not None else None)
    if result.x is None:
        return set(graph.roots), 'proven_infeasible' if result.status==2 else 'solver_no_incumbent', diagnostic
    retained = {b for b in blobs if result.x[index[b]]>.5}
    size = metadata+sum(sizes[b] for b in retained)
    covered = (certificate(graph,retained)['complete'] if alternative
               else graph.coverage(retained)[0])
    valid = graph.roots <= retained and covered and (budget is None or size <= budget)
    modeled_bytes = float(result.fun)*1024+metadata
    valid = valid and math.isclose(size,modeled_bytes,rel_tol=1e-9,abs_tol=1e-5)
    diagnostic.update(retained_bytes=size, postchecked=valid, complete=covered)
    return retained, 'ok' if valid else 'solver_incumbent_rejected', diagnostic
