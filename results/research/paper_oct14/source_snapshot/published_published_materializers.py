"""Pinned original HYPPO materialization component with an explicit adapter.

We execute the original component unchanged, not the full HYPPO execution
system. The physical-blob graph and cost/frequency annotations are ours.
No third-party source is redistributed by this project.
"""
import importlib.util
import urllib.request
from pathlib import Path
from .core import digest

REPOSITORY='akontaxakis/HYPPO'
REVISION='405e42de863272fcb71a625cf6b2ae0696c7a8c5'
SOURCE_SHA256='b857a387b81127585cb19a5925f1b1a84ed63361db5184ea3c84f8adc864765a'
URL=f'https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/Components/history_manager.py'


def load_source(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    path=directory/'history_manager.py'
    if not path.exists():path.write_bytes(urllib.request.urlopen(URL,timeout=60).read())
    if digest(path.read_bytes())!=SOURCE_SHA256:raise ValueError('Pinned HYPPO source hash mismatch')
    spec=importlib.util.spec_from_file_location('recoverml_pinned_hyppo_history',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def adapt(graph):
    import networkx as nx
    result=nx.DiGraph();costs={};ancestors={}
    def lineage(nid):
        if nid in costs:return costs[nid],ancestors[nid]
        node=graph.nodes[nid];visited={nid}
        for parent in node.deps:visited|=lineage(parent)[1]
        ancestors[nid]=visited;costs[nid]=sum(graph.nodes[v].compute_s for v in visited)
        return costs[nid],visited
    for nid in graph.nodes:lineage(nid)
    frequency={b:0 for b in graph.candidates}
    dependencies={b:set() for b in graph.candidates}
    for node in graph.nodes.values():dependencies[node.blob]|={graph.nodes[d].blob for d in node.deps}
    for targets in graph.targets.values():
        todo=[graph.nodes[t].blob for t in targets];seen=set()
        while todo:
            blob=todo.pop()
            if blob in seen:continue
            seen.add(blob);todo.extend(dependencies[blob]-seen)
        for blob in seen:frequency[blob]+=1
    for blob,size in graph.sizes().items():
        nodes=[n for n in graph.nodes.values() if n.blob==blob]
        result.add_node(blob,type='raw' if blob in graph.roots else 'artifact',
            cc=max(costs[n.id] for n in nodes),size=size,frequency=max(1,frequency[blob]))
    return result


def select(graph,optional_budget,module,frequency=False):
    adapted=adapt(graph)
    # Original source uses a strict Budget > used + size test. Artifact sizes
    # are integers, so +1 gives the inclusive <= budget used by all comparators
    # without modifying the original component or awarding extra usable bytes.
    native_budget=optional_budget+1
    chosen=(module.rank_based_materializer_frequency(adapted.nodes,native_budget)
            if frequency else module.rank_based_materializer(adapted,native_budget))
    if sum(graph.sizes()[b] for b in chosen)>optional_budget:
        raise RuntimeError('Published component exceeded inclusive optional budget')
    return graph.roots|set(chosen)
