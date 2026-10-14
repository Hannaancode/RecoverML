import itertools
import random
import unittest
from recoverml.core import Graph
from recoverml.witness import certificate


def scan_reference(graph,retained):
    available=set(retained);steps=[dict(blob=b,action='load') for b in sorted(retained)]
    producers=sorted(graph.nodes.values(),key=lambda n:(n.compute_s,n.id));round_number=0
    while True:
        previous=set(available);added=set()
        for node in producers:
            if node.blob in available or not node.replayable:continue
            deps=[graph.nodes[d].blob for d in node.deps]
            if all(b in previous for b in deps):
                available.add(node.blob);added.add(node.blob)
                steps.append(dict(blob=node.blob,action='replay',producer=node.id,dependencies=deps,round=round_number))
        if not added:break
        round_number+=1
    coverage={v:all(graph.nodes[t].blob in available for t in ts) for v,ts in graph.targets.items()}
    return dict(complete=all(coverage.values()),version_coverage=coverage,steps=steps,
        available=sorted(available),semantics='exact artifact bytes; original events are not reproduced')


class IndexTests(unittest.TestCase):
    def test_exact_producer_order_and_rounds_match_scan_with_aliases(self):
        rng=random.Random(7492)
        for case in range(48):
            graph=Graph(env={});ids=[]
            for i in range(8):
                deps=[rng.choice(ids) for _ in range(rng.randrange(4))] if ids else []
                ids.append(graph.add('test',deps,dict(i=i),rng.randrange(5),rng.choice([False,True]),
                    str(i),rng.randrange(3)/100.,case,mandatory=i==0))
            graph.targets={'0':ids[-3:]};optional=sorted(graph.candidates-graph.roots)
            for flags in itertools.product([False,True],repeat=len(optional)):
                retained=graph.roots|{b for b,flag in zip(optional,flags) if flag}
                self.assertEqual(certificate(graph,retained),scan_reference(graph,retained))
