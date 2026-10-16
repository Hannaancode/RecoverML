"""Direct retention heuristics for the SAME bounded group-loss contract.

These are our simple baselines, not published algorithms or certified optima.
Forward selection scores grounded version/scenario coverage per added byte.
The stronger baseline also reverse-deletes from the full physical store and
tries one-added-artifact exchanges followed by another deletion pass.
All feasibility checks enumerate the allowed faults and use grounded closure.
"""
import itertools
import math
import time
from .capability_retention import validate, restricted, retained_bytes
from .witness import certificate


def fault_sets(capabilities, k, maximum_scenarios=2000):
    groups=sorted(set(capabilities.values()))
    count=sum(math.comb(len(groups),i) for i in range(min(k,len(groups))+1))
    if count>maximum_scenarios:
        raise ValueError('Heuristic scenario limit exceeded')
    return [tuple(f) for i in range(min(k,len(groups))+1)
            for f in itertools.combinations(groups,i)]


class Coverage:
    def __init__(self, graph, capabilities, k):
        self.views=[restricted(graph,capabilities,f) for f in fault_sets(capabilities,k)]
        self.maximum=len(self.views)*len(graph.targets)
        self.weight=len(self.views)*len(graph.candidates)+1
        self.cache={}

    def score(self, selected):
        key=frozenset(selected)
        if key not in self.cache:
            certs=[certificate(g,selected) for g in self.views]
            versions=sum(sum(c['version_coverage'].values()) for c in certs)
            grounded=sum(len(c['available']) for c in certs)
            self.cache[key]=(versions,grounded)
        return self.cache[key]

    def complete(self, selected):
        return self.score(selected)[0]==self.maximum


def _order(graph, values, reverse=False):
    return sorted(values,reverse=reverse)


def _forward(graph, capabilities, k, budget, coverage, reverse=False):
    selected=set(graph.roots);sizes=graph.sizes()
    while not coverage.complete(selected):
        current=coverage.score(selected);choices=[]
        for blob in _order(graph,graph.candidates-selected,reverse):
            if retained_bytes(graph,selected|{blob},capabilities,k)>budget:continue
            after=coverage.score(selected|{blob})
            gain=(after[0]-current[0])*coverage.weight+after[1]-current[1]
            if gain>0:choices.append((gain/max(1,sizes[blob]),blob))
        if not choices:break
        # Stable iteration order is the declared tie policy.
        best=max(choices,key=lambda item:item[0])[1];selected.add(best)
    return selected


def _prune(graph, selected, coverage, reverse=False):
    sizes=graph.sizes()
    order=sorted(selected-graph.roots,key=lambda b:(-sizes[b],b),reverse=False)
    if reverse:
        # Reverse hash order only within equal-size groups.
        order=sorted(selected-graph.roots,key=lambda b:b,reverse=True)
        order.sort(key=lambda b:-sizes[b])
    selected=set(selected)
    for blob in order:
        trial=selected-{blob}
        if coverage.complete(trial):selected=trial
    return selected


def select(graph, capabilities, k, budget, local_improvement=False,
           reverse_ties=False, maximum_exchange_passes=2):
    validate(graph,capabilities,k)
    if not isinstance(budget,int) or budget<0:raise ValueError('Integer byte budget required')
    if retained_bytes(graph,graph.roots,capabilities,k)>budget:
        raise ValueError('Budget excludes mandatory roots and metadata')
    started=time.perf_counter();coverage=Coverage(graph,capabilities,k)
    forward=_forward(graph,capabilities,k,budget,coverage,reverse_ties)
    selected=forward;exchanges=0
    if local_improvement:
        robust=_prune(graph,set(graph.candidates),coverage,reverse_ties)
        sizes=graph.sizes()
        for _ in range(maximum_exchange_passes):
            best=robust;best_size=sum(sizes[b] for b in best)
            for blob in _order(graph,graph.candidates-robust,reverse_ties):
                candidate=_prune(graph,robust|{blob},coverage,reverse_ties)
                size=sum(sizes[b] for b in candidate)
                if size<best_size:best=candidate;best_size=size
            if best==robust:break
            robust=best;exchanges+=1
        if retained_bytes(graph,robust,capabilities,k)<=budget:
            if (coverage.score(robust)[0],-retained_bytes(graph,robust,capabilities,k)) >= (
                    coverage.score(forward)[0],-retained_bytes(graph,forward,capabilities,k)):
                selected=robust
    actual=retained_bytes(graph,selected,capabilities,k)
    assert graph.roots<=selected and actual<=budget
    return selected,dict(robust_certified=coverage.complete(selected),storage_optimal=False,
        retained_bytes=actual,coverage_version_scenarios=coverage.score(selected)[0],
        total_version_scenarios=coverage.maximum,planning_s=time.perf_counter()-started,
        unique_closure_evaluations=len(coverage.cache),exchange_passes=exchanges,
        algorithm='forward_plus_reverse_delete_exchange' if local_improvement else 'forward_greedy',
        tie_order='reverse_hash' if reverse_ties else 'hash')
