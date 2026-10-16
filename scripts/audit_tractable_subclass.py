"""Independent finite checks of a single-producer DAG retention reduction.

This script changes no planner or benchmark code and measures no timings.
The generated specification and closure and max-flow implementations use only
the standard library. Actual capture inspection reads manifests only.
"""
import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path


def subsets(values):
    values = tuple(values)
    return [frozenset(c) for n in range(len(values)+1) for c in itertools.combinations(values, n)]


def closure(producers, retained, disabled):
    available = set(retained)
    while True:
        following = available | {b for b, rules in enumerate(producers)
            if any(group not in disabled and set(deps) <= available for deps, group in rules)}
        if following == available: return frozenset(available)
        available = following


def cut(producers, roots, targets, sizes, disable_groups):
    """Standard integer-capacity node splitting and Edmonds-Karp max-flow."""
    n = len(producers); source = 2*n; sink = source+1; size = sink+1
    capacity = [[0]*size for _ in range(size)]
    infinity = sum(sizes)+1
    for b, rules in enumerate(producers):
        if b in roots: continue
        capacity[2*b][2*b+1] = sizes[b]
        if not rules or disable_groups and rules[0][1] is not None:
            capacity[source][2*b] = infinity
        else:
            for d in rules[0][0]:
                if d not in roots: capacity[2*d+1][2*b] = infinity
        if b in targets: capacity[2*b+1][sink] = infinity
    residual = [row[:] for row in capacity]; flow = 0
    while True:
        parent = [-1]*size; parent[source] = source; todo = deque([source])
        while todo and parent[sink] < 0:
            u = todo.popleft()
            for v, remaining in enumerate(residual[u]):
                if remaining > 0 and parent[v] < 0:
                    parent[v] = u; todo.append(v)
        if parent[sink] < 0: break
        amount = infinity; v = sink
        while v != source:
            amount = min(amount, residual[parent[v]][v]); v = parent[v]
        v = sink
        while v != source:
            u = parent[v]; residual[u][v] -= amount; residual[v][u] += amount; v = u
        flow += amount
    reachable = {source}; todo = [source]
    while todo:
        u = todo.pop()
        for v, remaining in enumerate(residual[u]):
            if remaining > 0 and v not in reachable: reachable.add(v); todo.append(v)
    selected = set(roots) | {b for b in range(n) if 2*b in reachable and 2*b+1 not in reachable}
    return flow, frozenset(selected)


def exhaustive():
    n = 4; roots = frozenset([0]); optional = tuple(range(1, n))
    choices = []
    for b in optional:
        choices.append([[]] + [[(deps, group)] for deps in subsets(range(b)) for group in (None, "A", "B")])
    stores = [roots | selected for selected in subsets(optional)]
    targets_list = [t for t in subsets(optional) if t]
    weights = ([0, 1, 1, 1], [0, 1, 2, 7], [0, 9, 3, 1], [0, 0, 3, 8])
    graphs = closure_comparisons = optimization_comparisons = 0
    for selected_rules in itertools.product(*choices):
        producers = [[]] + list(selected_rules)
        groups = frozenset(g for rules in producers for _, g in rules if g is not None)
        single_faults = [frozenset()] + [frozenset([g]) for g in groups]
        robust_closures, ordinary_closures = {}, {}
        for store in stores:
            by_single = frozenset.intersection(*(closure(producers, store, f) for f in single_faults))
            by_all = closure(producers, store, groups)
            if by_single != by_all:
                raise AssertionError(dict(error="Closure equivalence failed", producers=producers, store=sorted(store)))
            robust_closures[store] = by_all
            ordinary_closures[store] = closure(producers, store, frozenset())
            closure_comparisons += 1
        for targets, sizes, disabled in itertools.product(targets_list, weights, (False, True)):
            available = robust_closures if disabled else ordinary_closures
            optimum = min(sum(sizes[b] for b in store-roots) for store in stores if targets <= available[store])
            predicted, chosen = cut(producers, roots, targets, sizes, disabled)
            if predicted != optimum or not targets <= available[chosen]:
                raise AssertionError(dict(error="Minimum-cut reduction failed", producers=producers,
                    targets=sorted(targets), sizes=sizes, disabled=disabled, predicted=predicted, optimum=optimum))
            optimization_comparisons += 1
        graphs += 1
    return dict(physical_DAG_specifications=graphs, mandatory_roots=[0], artifacts_per_graph=n,
        every_earlier_dependency_subset=True, producer_options=["none", "ungrouped", "A", "B"],
        fixed_store_closure_comparisons=closure_comparisons, target_subsets_per_graph=len(targets_list),
        byte_weight_profiles=weights, k0_and_kge1_minimum_cut_vs_exhaustive_comparisons=optimization_comparisons,
        interpretation="Finite exhaustive validation supports the accompanying general proof and does not replace it")


def inspect_manifest(path):
    data = json.loads(path.read_text()); roots = set(data["mandatory_blobs"])
    nodes = {n["id"]: n for n in data["nodes"]}; blobs = {n["blob"] for n in nodes.values()}
    producers = Counter(n["blob"] for n in nodes.values() if n["replayable"] and n["blob"] not in roots)
    adjacency = {b:set() for b in blobs-roots}; incoming = {b:0 for b in adjacency}
    for node in nodes.values():
        if not node["replayable"] or node["blob"] in roots: continue
        for dep in {nodes[d]["blob"] for d in node["deps"]}-roots:
            if node["blob"] not in adjacency[dep]:
                adjacency[dep].add(node["blob"]); incoming[node["blob"]] += 1
    todo = [b for b in incoming if incoming[b] == 0]; ordered = 0
    while todo:
        current = todo.pop(); ordered += 1
        for following in adjacency[current]:
            incoming[following] -= 1
            if incoming[following] == 0: todo.append(following)
    acyclic = ordered == len(incoming); unique = all(c <= 1 for c in producers.values())
    return dict(path=path.as_posix(), manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        logical_nodes=len(nodes), physical_artifacts=len(blobs), nonroot_artifacts=len(blobs-roots),
        multiple_replayable_producer_blobs=sum(c>1 for c in producers.values()),
        root_conditioned_physical_DAG=acyclic, at_most_one_producer=unique, qualifies=acyclic and unique)


def run(output):
    if output.exists(): raise ValueError("Refusing to overwrite validation evidence")
    result = exhaustive()
    paths = sorted(Path("results/research/scientific_sensitivity_oct15_inputs").glob("*/manifest.json"))
    retinal = sorted(Path("results/research/eyeai_rebuild_oct15/captures").glob("*/manifest.json"))
    inspected = [inspect_manifest(p) for p in paths+retinal]
    # OR alternatives survive either individual failure while both disabled fail.
    alternatives = [[], [((0,), "A"), ((0,), "B")]]
    or_single = all(1 in closure(alternatives, {0}, {g}) for g in ("A", "B"))
    or_all = 1 in closure(alternatives, {0}, {"A", "B"})
    assert or_single and not or_all
    # Without a DAG, ungrounded cycles have no opaque failure source for the cut.
    cycle = [[], [((2,), None)], [((1,), None)]]
    cycle_flow, _ = cut(cycle, {0}, {1}, [0,3,5], False)
    cycle_optimum = min(sum([0,3,5][b] for b in s) for s in subsets(range(3)) if {0} <= s and 1 in closure(cycle, s, set()))
    assert cycle_flow == 0 and cycle_optimum == 3
    report = dict(status="PASS", created_utc=datetime.now(timezone.utc).isoformat(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), exhaustive=result,
        actual_capture_inventory=inspected, actual_scientific_histories=len(paths),
        actual_scientific_qualifying=sum(r["qualifies"] for r in inspected[:len(paths)]),
        actual_retinal_histories_currently_present=len(retinal),
        actual_retinal_qualifying=sum(r["qualifies"] for r in inspected[len(paths):]),
        outside_scope_counterexamples=dict(two_OR_producers={"single_group_robust":or_single,"recoverable_after_all_groups_removed":or_all},
            ungrounded_cycle={"naive_cut_bytes":cycle_flow,"actual_minimum_bytes":cycle_optimum}),
        errors=[], limitations=["All standard-library checks are structural and no payload or timing is measured",
            "Retinal inventory is a snapshot of manifests present at this receipt time rather than a declaration that its full benchmark finished",
            "Finite enumeration uses four physical artifacts and two labels; the general scope follows from the separate proof",
            "No new optimization architecture or min-cut algorithm is claimed"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
