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
    # Index once per call: independent branches must not repeatedly scan the
    # entire captured history. Keep all physical aliases and insertion order.
    by_blob={}
    order={nid:i for i,nid in enumerate(graph.nodes)}
    for node in graph.nodes.values():by_blob.setdefault(node.blob,[]).append(node)
    target_index={}
    for position,(version,target) in enumerate((v,t) for v,ts in graph.targets.items() for t in ts):
        target_index.setdefault(graph.nodes[target].blob,[]).append((position,version,target))
    retained=set(graph.roots);records=[]
    for component in components(graph):
        if not component&targets:continue
        if len(component)==1:
            blob=next(iter(component));providers=[n for n in by_blob[blob]
                if n.replayable and n.blob==blob and {graph.nodes[d].blob for d in n.deps}<=graph.roots]
            groups={capabilities[n.id] for n in providers if n.id in capabilities}
            survives=any(n.id not in capabilities for n in providers) or len(groups)>k
            if not survives:retained.add(blob)
            records.append(dict(kind='root_provider_exact',optional_blobs=1,
                root_producer_groups=len(groups),retained_target=not survives))
            continue
        local_nodes=[n for blob in component for n in by_blob[blob]]
        live=[n for n in local_nodes if n.replayable]
        needed_roots={graph.nodes[d].blob for n in live for d in n.deps}&graph.roots
        projected=Graph(env=graph.env);projected.roots=set(needed_roots)
        projection=local_nodes+[n for blob in needed_roots for n in by_blob[blob]]
        for node in sorted(projection,key=lambda n:order[n.id]):
            nid=node.id
            # Opaque ancestry is provenance, not an executable dependency.
            # Root producers are not needed because these values are fixed.
            projected.nodes[nid]=(replace(node,deps=[],replayable=False)
                if node.blob in needed_roots or not node.replayable else node)
        projected.targets={}
        for _,version,target in sorted(row for blob in component for row in target_index.get(blob,())):
            projected.targets.setdefault(version,[]).append(target)
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
