"""Offline policies; selected sets are materialized only after planning.

Reverse deletion is a heuristic. Failure to fit does NOT prove infeasibility.
The exact oracle on small graphs enumerates subsets and does prove feasibility.
"""
import itertools
import time
from dataclasses import dataclass, field
from .core import Graph


@dataclass
class Selection:
    policy: str
    retained: set[str]
    status: str
    planning_s: float
    history: list[dict] = field(default_factory=list)


def select(g: Graph, policy: str, budget: int) -> Selection:
    start = time.perf_counter()
    sizes = g.sizes()
    metadata = g.metadata_bytes()
    def used(s):
        return metadata + sum(sizes[b] for b in s)
    def result(s, status='ok', history=None):
        if used(s) > budget and status == 'ok':
            status = 'budget_exceeded'
        return Selection(policy, s, status, time.perf_counter()-start, history or [])
    if used(g.roots) > budget:
        return result(set(g.roots), 'required_inputs_exceed_budget')
    if policy == 'full_snapshot':
        return result(g.candidates)
    if policy == 'full_replay':
        return result(set(g.roots))
    if policy == 'target_snapshots':
        # Strong trivial baseline: protect requested outputs directly, not intermediates.
        s = g.roots | {g.nodes[t].blob for ts in g.targets.values() for t in ts}
        return result(s)
    if policy in ('recoverability_v2','recoverability_v3'):
        from .optimizer import optimize
        s,status,history = optimize(g,budget,sizes=sizes,metadata=metadata,
                                    prune_opaque=policy=='recoverability_v3')
        if status in ('solver_no_incumbent','solver_incumbent_rejected'):
            fallback = select(g,'recoverability',budget)
            history.append(dict(strategy='heuristic_fallback',status=fallback.status,
                                eviction_trace=fallback.history))
            return result(fallback.retained,fallback.status,history)
        return result(s,status,history)
    nodes_by_blob = {}
    for n in g.nodes.values():
        nodes_by_blob.setdefault(n.blob, []).append(n)
    if policy in ('cost_cache', 'pinned_cost'):
        s = set(g.roots)
        if policy == 'pinned_cost':
            s |= {n.blob for n in g.nodes.values() if not n.replayable}
        if used(s) > budget:
            return result(s, 'required_pins_exceed_budget')
        # Measured operation time / physical blob bytes. No restoration oracle data.
        ranked = sorted(g.candidates-s, key=lambda b:(
            -sum(n.compute_s for n in nodes_by_blob[b])/sizes[b], b))
        for b in ranked:
            if used(s) + sizes[b] <= budget:
                s.add(b)
        return result(s)
    if policy != 'recoverability':
        raise ValueError(policy)
    def prune(seed, label):
        s = set(seed)
        history = []
        current_cost = g.estimate(s)
        while True:
            choices = []
            for b in sorted(s-g.roots):
                candidate = s-{b}
                if not g.coverage(candidate)[0]:
                    continue
                cost = g.estimate(candidate)
                increment = cost-current_cost
                if used(s) <= budget and increment > 1e-12:
                    continue
                choices.append((max(increment,0.0)/sizes[b], -sizes[b], b, cost))
            if not choices:
                break
            _, _, b, next_cost = min(choices)
            s.remove(b)
            history.append(dict(seed=label, removed_blob=b, bytes_saved=sizes[b],
                                estimated_cost_before_s=current_cost,
                                estimated_cost_after_s=next_cost, all_targets_recoverable=True))
            current_cost = next_cost
        # Marginal-benefit additions account for shared dependencies across requests.
        # Optional cache entries are added only if they lower estimated latency.
        if used(s) <= budget:
            while True:
                choices = []
                for b in sorted(g.candidates-s):
                    if used(s)+sizes[b] > budget:
                        continue
                    cost = g.estimate(s|{b})
                    gain = current_cost-cost
                    if gain > 1e-12:
                        choices.append((-gain/sizes[b],b,cost))
                if not choices:
                    break
                _,b,cost = min(choices)
                s.add(b)
                history.append(dict(seed=label, added_blob=b, bytes_added=sizes[b],
                                    estimated_cost_before_s=current_cost,
                                    estimated_cost_after_s=cost, all_targets_recoverable=True))
                current_cost=cost
        return s,current_cost,history
    # Independent feasible structural seeds reduce reverse-deletion local traps.
    # This is still heuristic, not a minimum-storage or optimal-latency proof.
    target_seed=g.roots | {g.nodes[t].blob for ts in g.targets.values() for t in ts}
    boundary_seed=g.roots | {n.blob for n in g.nodes.values() if not n.replayable}
    candidates=[prune(g.candidates,'all_artifacts'),
                prune(target_seed,'direct_targets'),prune(boundary_seed,'opaque_boundaries')]
    fitted=[c for c in candidates if used(c[0]) <= budget]
    if not fitted:
        s,cost,history=min(candidates,key=lambda c:used(c[0]))
        return result(s,'heuristic_cannot_fit',history)
    s,cost,history=min(fitted,key=lambda c:(c[1],used(c[0]),sorted(c[0])))
    return result(s,history=history)


def exact(g: Graph, budget: int | None = None, max_optional: int = 18) -> dict:
    """Enumerate all subsets for tiny graphs; minimize bytes or estimated latency."""
    start = time.perf_counter()
    optional = sorted(g.candidates-g.roots)
    if len(optional) > max_optional:
        raise ValueError('Exact oracle restricted to small graphs')
    best_set = None
    best_value = float('inf')
    feasible = 0
    for mask in itertools.product((False,True), repeat=len(optional)):
        s = g.roots | {b for b, keep in zip(optional,mask) if keep}
        size = g.size(s)
        if budget is not None and size > budget:
            continue
        if not g.coverage(s)[0]:
            continue
        feasible += 1
        value = size if budget is None else g.estimate(s)
        if value < best_value:
            best_value, best_set = value, s
    return dict(feasible=best_set is not None, objective=best_value if best_set else None,
                retained=sorted(best_set) if best_set else [], subsets_tested=2**len(optional),
                feasible_subsets=feasible, planning_s=time.perf_counter()-start)
