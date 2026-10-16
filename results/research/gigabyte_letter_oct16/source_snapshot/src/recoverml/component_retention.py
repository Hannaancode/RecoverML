"""Exact root-conditioned decomposition of the physical recovery problem.

Shared failure labels do not couple retention variables in separate live
producer components under a universal bounded-loss contract. Mandatory roots
are removed from the connectivity graph and paid once in the original store.
Internal solver projections are never written as capture manifests.
"""
from dataclasses import replace
import math
from .core import Graph
from .capability_retention import validate,retained_bytes
from .robust_retention import optimize as select_engine


def components(graph):
    optional=graph.candidates-graph.roots;parent={b:b for b in optional}
    def find(b):
        while parent[b]!=b:parent[b]=parent[parent[b]];b=parent[b]
        return b
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    for node in graph.nodes.values():
        if not node.replayable or node.blob in graph.roots:continue
        for dep in {graph.nodes[d].blob for d in node.deps}-graph.roots:union(node.blob,dep)
    result={}
    for b in optional:result.setdefault(find(b),set()).add(b)
    return sorted(result.values(),key=lambda s:min(s))


def optimize(graph,capabilities,k,time_limit_s=30.):
    validate(graph,capabilities,k)
    if time_limit_s<=0 or not math.isfinite(time_limit_s):raise ValueError('Positive finite time limit required')
    if any(not isinstance(s,int) or s<0 for s in graph.sizes().values()):raise ValueError('Invalid artifact byte size')
    targets={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    retained=set(graph.roots);records=[]
    for component in components(graph):
        if not component&targets:continue
        if len(component)==1:
            blob=next(iter(component));providers=[n for n in graph.nodes.values()
                if n.replayable and n.blob==blob and {graph.nodes[d].blob for d in n.deps}<=graph.roots]
            groups={capabilities[n.id] for n in providers if n.id in capabilities}
            survives=any(n.id not in capabilities for n in providers) or len(groups)>k
            if not survives:retained.add(blob)
            records.append(dict(kind='root_provider_exact',optional_blobs=1,
                root_producer_groups=len(groups),retained_target=not survives))
            continue
        live=[n for n in graph.nodes.values() if n.replayable and n.blob in component]
        needed_roots={graph.nodes[d].blob for n in live for d in n.deps}&graph.roots
        projected=Graph(env=graph.env);projected.roots=set(needed_roots)
        for nid,node in graph.nodes.items():
            if node.blob not in component|needed_roots:continue
            # Opaque ancestry is provenance, not an executable dependency.
            # Root producers are not needed because these values are fixed.
            projected.nodes[nid]=(replace(node,deps=[],replayable=False)
                if node.blob in needed_roots or not node.replayable else node)
        projected.targets={version:[t for t in ts if graph.nodes[t].blob in component]
            for version,ts in graph.targets.items() if any(graph.nodes[t].blob in component for t in ts)}
        local_caps={nid:group for nid,group in capabilities.items()
                    if nid in projected.nodes and projected.nodes[nid].replayable}
        chosen,status,diag=select_engine(projected,local_caps,k,time_limit_s=time_limit_s)
        records.append(dict(kind='solver_projection',optional_blobs=len(component),diagnostic=diag))
        if status!='ok' or not diag.get('robust_certified') or not diag.get('storage_optimal'):
            return retained,status,dict(robust_certified=False,storage_optimal=False,components=records)
        retained|=chosen&component
    return retained,'ok',dict(robust_certified=True,storage_optimal=True,
        retained_bytes=retained_bytes(graph,retained,capabilities,k),components=records,
        component_count=len(records),solver_components=sum(r['kind']=='solver_projection' for r in records),
        atomic_components=sum(r['kind']=='root_provider_exact' for r in records),
        objective='original global metadata and mandatory roots paid once')
