import itertools
import random
import unittest
from recoverml.core import Graph
from recoverml.robust_heuristics import select,fault_sets
from recoverml.capability_retention import retained_bytes
from test_capability_retention import independent_can


class RobustHeuristicTests(unittest.TestCase):
    def test_budget_and_independent_fault_coverage_on_random_alias_graphs(self):
        rng=random.Random(151026)
        for case in range(12):
            g=Graph(env={});ids=[];caps={}
            for i in range(8):
                deps=rng.sample(ids,min(len(ids),rng.randrange(3)))
                nid=g.add('fixture',deps,dict(i=i),rng.randrange(5),i%3!=0,'case',.01,i,mandatory=i==0)
                ids.append(nid)
                if g.nodes[nid].replayable:caps[nid]='g'+str(i%3)
            g.targets={'0':ids[-2:]};k=1
            fixed=retained_bytes(g,g.roots,caps,k);full=retained_bytes(g,g.candidates,caps,k)
            for budget in (fixed,(fixed+full)//2,full):
                for local in (False,True):
                    chosen,diag=select(g,caps,k,budget,local)
                    self.assertLessEqual(retained_bytes(g,chosen,caps,k),budget)
                    independent=all(independent_can(g,chosen,caps,f) for f in fault_sets(caps,k))
                    self.assertEqual(independent,diag['robust_certified'])
                    self.assertFalse(diag['storage_optimal'])
                    if budget==full:self.assertTrue(independent)

    def test_unsafe_exponential_scenario_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'scenario limit'):
            fault_sets({str(i):str(i) for i in range(40)},4)


if __name__=='__main__':unittest.main()
