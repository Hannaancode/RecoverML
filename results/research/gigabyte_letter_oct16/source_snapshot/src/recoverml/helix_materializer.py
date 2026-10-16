"""HELIX Streaming OMP reimplementation with a disclosed capture DAG adapter.

PVLDB 12(4) Algorithm 2 and Definition 6 select an out-of-scope node when
cumulative compute exceeds twice load time and its size fits the remaining
budget. This is the published decision rule, not native HELIX execution.
"""
import math
PAPER_URL='https://www.vldb.org/pvldb/vol12/p446-xin.pdf'


def select(graph,optional_budget,read_bytes_s,reverse_ties=False):
    if not isinstance(optional_budget,int) or optional_budget<0:raise ValueError('Nonnegative integer budget required')
    if read_bytes_s<=0 or not math.isfinite(read_bytes_s):raise ValueError('Positive finite read speed required')
    order=list(graph.nodes);position={n:i for i,n in enumerate(order)}
    ancestors={};end={n:position[n] for n in order}
    for nid,node in graph.nodes.items():
        visited={nid}
        for dep in set(node.deps):
            if position[dep]>=position[nid]:raise ValueError('Capture must be topological')
            visited|=ancestors[dep];end[dep]=max(end[dep],position[nid])
        ancestors[nid]=visited
    events={}
    for nid in order:events.setdefault(end[nid],[]).append(nid)
    retained=set(graph.roots);remaining=optional_budget;decisions=[]
    for event in sorted(events):
        for nid in events[event][::-1] if reverse_ties else events[event]:
            node=graph.nodes[nid]
            if node.blob in retained:continue
            cumulative=sum(graph.nodes[a].compute_s for a in ancestors[nid]);load=node.size/read_bytes_s
            accept=cumulative>2*load and remaining>=node.size
            decisions.append(dict(node=nid,event=event,cumulative_s=cumulative,load_s=load,materialized=accept))
            if accept:retained.add(node.blob);remaining-=node.size
    assert sum(graph.sizes()[b] for b in retained-graph.roots)<=optional_budget
    return retained,dict(paper=PAPER_URL,algorithm='Algorithm 2 and Definition 6',read_bytes_s=read_bytes_s,
        reverse_ties=reverse_ties,decisions=decisions,scope='Paper rule reimplementation with logical capture schedule and physical payload adapter')
