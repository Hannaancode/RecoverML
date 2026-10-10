"""Budgeted global checkpoint planning for the existing load-first executor.

Optimality refers to the additive capture-time cost model, not measured future
latency. A bounded MILP may return an incumbent without proving optimality.
"""
import math
import time


READ_LATENCY_S = 2e-5
READ_BANDWIDTH = 500e6


def read_cost(node):
    return READ_LATENCY_S + node.size / READ_BANDWIDTH


def optimize(g, budget, time_limit_s=0.5, *, sizes=None, metadata=None,
             prune_opaque=False, compact=False):
    sizes = g.sizes() if sizes is None else sizes
    metadata = g.metadata_bytes() if metadata is None else metadata
    targets = g.roots | {g.nodes[t].blob for ts in g.targets.values() for t in ts}
    target_bytes = metadata + sum(sizes[b] for b in targets)
    # Every distinct target in a request must be produced at least once. If
    # loading it costs no more than its own replay (before any dependencies),
    # direct target loads attain a lower bound on ANY valid request plan.
    # Non-replayable targets can only be loaded. This test is conservative.
    lower_bound = sum(read_cost(g.nodes[t]) for ts in g.targets.values() for t in set(ts))
    if target_bytes <= budget and all(
        not g.nodes[t].replayable or read_cost(g.nodes[t]) <= g.nodes[t].compute_s
        for ts in g.targets.values() for t in ts
    ):
        return targets, 'ok', [dict(strategy='direct_target_lower_bound',
            estimated_optimal=True, estimated_cost_s=lower_bound,
            all_targets_recoverable=True)]

    # Imports are lazy so direct-target planning does not invoke the solver.
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import coo_matrix

    # Non replayable nodes can only be loaded. Their parents never need to be
    # produced solely for that load, while parents used elsewhere remain reachable.
    ancestry = {}
    for version, ts in g.targets.items():
        ancestors, visiting = set(), set()
        def walk(nid):
            if nid in visiting:
                raise ValueError('Cyclic graph')
            if nid in ancestors:
                return
            visiting.add(nid)
            if not prune_opaque or g.nodes[nid].replayable:
                for parent in g.nodes[nid].deps:
                    walk(parent)
            visiting.remove(nid)
            ancestors.add(nid)
        for target in ts:
            walk(target)
        ancestry[version] = ancestors
    eligible = g.roots | {g.nodes[n].blob for ancestors in ancestry.values() for n in ancestors}
    blobs = sorted(eligible if prune_opaque else g.candidates)
    # Roots are mandatory and therefore do not need binary storage variables in
    # the compact formulation. Their exact byte cost is moved to the right hand
    # side of the budget constraint.
    physical = [b for b in blobs if not compact or b not in g.roots]
    index = {b:i for i,b in enumerate(physical)}
    c = [0.0] * len(physical)
    lo = [1.0 if b in g.roots else 0.0 for b in physical]
    hi = [1.0] * len(physical)
    columns, rows, coefficients, lows, highs = [], [], [], [], []
    def constraint(terms, low=-np.inf, high=np.inf):
        row = len(lows)
        for col, value in terms.items():
            rows.append(row); columns.append(col); coefficients.append(value)
        lows.append(low); highs.append(high)
    # KiB coefficients keep the storage row reasonably scaled. Actual integer
    # bytes, coverage and estimated execution are checked after optimization.
    fixed_bytes = sum(sizes[b] for b in g.roots) if compact else 0
    constraint({index[b]:sizes[b]/1024 for b in physical},
               high=(budget-metadata-fixed_bytes)/1024)
    load_vars = {}
    replay_variable_count = 0
    for version, ts in g.targets.items():
        ancestors = ancestry[version]
        pairs = {}
        for nid in sorted(ancestors):
            n = g.nodes[nid]
            if not math.isfinite(n.compute_s) or n.compute_s < 0:
                raise ValueError('Replay cost must be finite and nonnegative')
            l = len(c)
            # A non-replayable node and a node whose blob is mandatory can
            # never use the replay branch. Omitting that fixed-zero binary is
            # an exact substitution rather than a heuristic.
            replay_disabled = compact and (not n.replayable or n.blob in g.roots)
            r = None if replay_disabled else l+1
            pairs[nid] = (l,r)
            load_vars[(version,nid)] = l
            # Objective in microseconds, matching Graph.estimate's summed
            # request costs with fresh memoization for each protected version.
            c.append(read_cost(n)*1e6)
            lo.append(0.); hi.append(1.)
            if r is not None:
                replay_variable_count += 1
                c.append(n.compute_s*1e6)
                lo.append(0.); hi.append(1. if n.replayable else 0.)
            active = {l:1.}
            if r is not None:
                active[r] = 1.
            constraint(active, low=1. if nid in ts else 0., high=1.)
            if n.blob not in g.roots:
                constraint({l:1.,index[n.blob]:-1.}, high=0.)
            # The runtime ALWAYS loads an available blob, so replay of a
            # retained node is prohibited in this optimization model too.
            if r is not None:
                if n.blob in g.roots:
                    hi[r] = 0.
                else:
                    constraint({r:1.,index[n.blob]:1.}, high=1.)
        for nid,(l,r) in pairs.items():
            if r is None or (prune_opaque and not g.nodes[nid].replayable):
                continue
            for parent in g.nodes[nid].deps:
                pl,pr = pairs[parent]
                terms = {r:1.,pl:-1.}
                if pr is not None:
                    terms[pr] = -1.
                constraint(terms, high=0.)
    matrix = coo_matrix((coefficients,(rows,columns)),shape=(len(lows),len(c))).tocsc()
    start = time.perf_counter()
    result = milp(np.asarray(c), integrality=np.ones(len(c)),
        bounds=Bounds(lo,hi), constraints=LinearConstraint(matrix,lows,highs),
        options={'time_limit':time_limit_s,'mip_rel_gap':0.0})
    strategy = ('bounded_global_milp_frontier_compact' if compact else
                'bounded_global_milp_pruned' if prune_opaque else 'bounded_global_milp')
    diag = dict(strategy=strategy, solver_status=int(result.status),
        solver_message=result.message, solver_s=time.perf_counter()-start,
        variables=len(c), constraints=len(lows), time_limit_s=time_limit_s,
        opaque_pruning=prune_opaque, compact_formulation=compact,
        physical_candidates=len(physical), fixed_physical_candidates=len(blobs)-len(physical),
        replay_variables=replay_variable_count,
        estimated_optimal=result.status==0,
        mip_gap=float(result.mip_gap) if getattr(result,'mip_gap',None) is not None else None)
    if result.x is None:
        return set(g.roots), 'proven_infeasible' if result.status==2 else 'solver_no_incumbent', [diag]
    # Remove optional blobs that no modeled request actually loads.
    retained = g.roots | {g.nodes[nid].blob for (v,nid),l in load_vars.items() if result.x[l]>.5}
    covered = g.coverage(retained)[0]
    size = metadata + sum(sizes[b] for b in retained)
    estimate = g.estimate(retained) if covered else float('inf')
    modeled = float(result.fun)/1e6
    valid = covered and size <= budget and math.isclose(estimate,modeled,rel_tol=1e-6,abs_tol=1e-9)
    diag.update(all_targets_recoverable=covered,retained_bytes=size,
                estimated_cost_s=estimate if covered else None,solver_objective_s=modeled,
                postchecked=valid)
    return retained, 'ok' if valid else 'solver_incumbent_rejected', [diag]
