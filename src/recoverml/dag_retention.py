"""Exact single-producer DAG retention using established integer minimum cut.

This specializes the already documented reduction in TRACTABLE_SUBCLASS_OCT15.
It is not a new max-flow algorithm. Cycles and alternative physical producers
are rejected, leaving the existing general exact engines available as fallback.
"""
from collections import deque
import math
import time

from .capability_retention import retained_bytes, validate
from .witness import certificate


def network(graph, capabilities, k):
    import networkx as nx
    validate(graph, capabilities, k)
    sizes = graph.sizes()
    if any(type(s) is not int or s < 0 for s in sizes.values()):
        raise ValueError('Nonnegative integer payload sizes required')
    if not graph.roots <= graph.candidates:
        raise ValueError('Unknown mandatory root')
    if any(n.size != sizes[n.blob] for n in graph.nodes.values()):
        raise ValueError('Conflicting sizes for one physical blob')
    optional = graph.candidates - graph.roots
    producers = {b: [] for b in optional}
    dag = nx.DiGraph()
    dag.add_nodes_from(sorted(optional))
    for n in graph.nodes.values():
        if n.blob not in optional or not n.replayable:
            continue
        producers[n.blob].append(n)
        for dependency in {graph.nodes[d].blob for d in n.deps} - graph.roots:
            dag.add_edge(dependency, n.blob)
    if any(len(ps) > 1 for ps in producers.values()):
        return None, 'multiple_physical_producers'
    if not nx.is_directed_acyclic_graph(dag):
        return None, 'physical_cycle'
    infinity = sum(sizes[b] for b in optional) + 1
    net = nx.DiGraph()
    net.add_nodes_from(['source', 'sink'])
    for b in sorted(optional):
        net.add_edge('i:' + b, 'o:' + b, capacity=sizes[b])
        ps = producers[b]
        if not ps or (k >= 1 and ps[0].id in capabilities):
            net.add_edge('source', 'i:' + b, capacity=infinity)
        else:
            for d in sorted({graph.nodes[n].blob for n in ps[0].deps} - graph.roots):
                net.add_edge('o:' + d, 'i:' + b, capacity=infinity)
    targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    for b in sorted(targets - graph.roots):
        net.add_edge('o:' + b, 'sink', capacity=infinity)
    return net, 'single_producer_physical_DAG'


def verify_proof(graph, capabilities, k, selected, proof):
    """Check an integer feasible flow and equal-cost cut without an optimizer.

    The standard max-flow/min-cut weak duality proves optimality when the
    feasible flow lower bound equals the feasible retained cut upper bound.
    """
    net, reason = network(graph, capabilities, k)
    if net is None:
        raise ValueError('Inapplicable cut proof: ' + reason)
    selected = set(selected)
    if not graph.roots <= selected <= graph.candidates:
        raise ValueError('Invalid retained set')
    flow_value = proof['optional_payload_lower_bound']
    if type(flow_value) is not int or flow_value < 0:
        raise ValueError('Invalid flow value')
    balance = {n: 0 for n in net}
    seen = set()
    for u, v, amount in proof['flow']:
        if (u, v) in seen or not net.has_edge(u, v):
            raise ValueError('Unknown or duplicate flow edge')
        seen.add((u, v))
        if type(amount) is not int or not 0 <= amount <= net[u][v]['capacity']:
            raise ValueError('Flow violates integer capacity')
        balance[u] -= amount
        balance[v] += amount
    if any(value != (-flow_value if n == 'source' else flow_value if n == 'sink' else 0)
           for n, value in balance.items()):
        raise ValueError('Flow conservation violated')
    # Delete paid vertices and check that no unavailable-source path reaches a
    # protected target. This does not trust the optimizer's cut partition.
    removed = {'i:' + b for b in selected - graph.roots}
    reached = {'source'}
    todo = deque(['source'])
    while todo:
        for v in net.successors(todo.popleft()):
            if v not in removed and v not in reached:
                reached.add(v)
                todo.append(v)
    if 'sink' in reached:
        raise ValueError('Retained vertices do not separate failures from targets')
    # Build the physical-size index once. Rebuilding it for each paid blob
    # made certificate checking quadratic on wide retained frontiers.
    sizes = graph.sizes()
    upper_bound = sum(sizes[b] for b in selected - graph.roots)
    if upper_bound != flow_value:
        raise ValueError('Flow lower bound and retained upper bound differ')
    return True


def optimize(graph, capabilities, k, time_limit_s=30.):
    import networkx as nx
    from dataclasses import replace
    if not math.isfinite(time_limit_s) or time_limit_s <= 0:
        raise ValueError('Positive finite time limit required')
    started = time.perf_counter()
    net, reason = network(graph, capabilities, k)
    if net is None:
        return set(graph.roots), 'not_applicable', dict(storage_optimal=False,
            robust_certified=False, reason=reason, selected_engine='dag_min_cut')
    value, flow = nx.maximum_flow(net, 'source', 'sink',
                                  flow_func=nx.algorithms.flow.preflow_push)
    residual = nx.DiGraph()
    residual.add_nodes_from(net)
    for u, v, data in net.edges(data=True):
        if data['capacity'] - flow[u][v] > 0:
            residual.add_edge(u, v)
        if flow[u][v] > 0:
            residual.add_edge(v, u)
    reached = nx.descendants(residual, 'source') | {'source'}
    selected = set(graph.roots) | {b for b in graph.candidates - graph.roots
        if 'i:' + b in reached and 'o:' + b not in reached}
    proof = dict(optional_payload_lower_bound=int(value),
        flow=[[u, v, int(amount)] for u in sorted(flow)
              for v, amount in sorted(flow[u].items()) if amount])
    verify_proof(graph, capabilities, k, selected, proof)
    # Independently check grounded recovery in the all-group-disabled view.
    # The unique-producer DAG theorem equates this to every allowed k>=1 loss.
    view = graph.__class__(env=graph.env)
    view.nodes = {nid: replace(n, replayable=n.replayable and not (k >= 1 and nid in capabilities))
                  for nid, n in graph.nodes.items()}
    view.roots = set(graph.roots)
    view.targets = graph.targets
    if not certificate(view, selected)['complete']:
        raise RuntimeError('Cut failed independent grounded recovery check')
    return selected, 'ok', dict(storage_optimal=True, robust_certified=True,
        retained_bytes=retained_bytes(graph, selected, capabilities, k),
        selected_engine='dag_min_cut', proof=proof, proof_verified=True,
        nodes=len(net), edges=net.number_of_edges(), planning_s=time.perf_counter()-started,
        attribution='Established integer max-flow/min-cut with vertex splitting',
        time_limit_scope='Validated for API compatibility; polynomial flow has no hard interruption deadline')
