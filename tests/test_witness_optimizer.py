import itertools
import random
import unittest
from recoverml.core import Graph
from recoverml.witness_optimizer import optimize


class WitnessOptimizerTests(unittest.TestCase):
    def test_storage_optimum_matches_independent_path_oracle(self):
        rng = random.Random(719)
        for case in range(32):
            graph = Graph(env={}); ids=[]
            for i in range(8):
                deps=rng.sample(ids,min(len(ids),rng.randrange(3)))
                ids.append(graph.add('test',deps,{'i':i},rng.randrange(5),
                    rng.choice([True,False]),str(i),.01,case,mandatory=i==0))
            graph.targets={'0':ids[-2:]}
            producers={}
            for n in graph.nodes.values():
                if n.replayable: producers.setdefault(n.blob,[]).append(n)
            def possible(blob,retained,path):
                if blob in retained: return True
                if blob in path: return False
                return any(all(possible(graph.nodes[d].blob,retained,path|{blob}) for d in n.deps)
                           for n in producers.get(blob,[]))
            optional=sorted(graph.candidates-graph.roots)
            best=float('inf')
            for flags in itertools.product([False,True],repeat=len(optional)):
                retained=graph.roots|{b for b,flag in zip(optional,flags) if flag}
                if all(possible(graph.nodes[t].blob,retained,set()) for t in ids[-2:]):
                    best=min(best,graph.size(retained))
            retained,status,diag=optimize(graph)
            self.assertEqual(status,'ok'); self.assertTrue(diag['storage_optimal'])
            self.assertEqual(graph.size(retained),best)
            _,status,_=optimize(graph,budget=best-1)
            self.assertEqual(status,'proven_infeasible')
            # Independent logical path oracle for a storage-matched baseline.
            def logical(nid,retained):
                n=graph.nodes[nid]
                return n.blob in retained or (n.replayable and all(logical(d,retained) for d in n.deps))
            best_logical=float('inf')
            for flags in itertools.product([False,True],repeat=len(optional)):
                retained=graph.roots|{b for b,flag in zip(optional,flags) if flag}
                if all(logical(t,retained) for t in ids[-2:]):
                    best_logical=min(best_logical,graph.size(retained))
            retained,status,diag=optimize(graph,alternative=False)
            self.assertEqual(status,'ok'); self.assertTrue(diag['storage_optimal'])
            self.assertEqual(graph.size(retained),best_logical)

    def test_alias_cycle_requires_a_retained_start(self):
        graph=Graph(env={})
        root=graph.add('input',[],{},0,False,'root',0.,0)
        same=graph.add('identity',[root],{},0,True,'identity',.01,0)
        graph.targets={'0':[same]}
        retained,status,diag=optimize(graph)
        self.assertEqual(status,'ok')
        self.assertEqual(retained,{graph.nodes[root].blob})
        self.assertTrue(diag['postchecked'])

    def test_empty_graph_and_invalid_limit(self):
        graph=Graph(env={})
        self.assertEqual(optimize(graph)[1],'ok')
        self.assertEqual(optimize(graph,budget=0)[1],'proven_infeasible')
        with self.assertRaises(ValueError): optimize(graph,time_limit_s=0)
