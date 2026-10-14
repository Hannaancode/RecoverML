import itertools
import random
import unittest
from recoverml.core import Graph
from recoverml.capability_retention import optimize, retained_bytes
from recoverml.scenario_retention import optimize as expanded
from test_capability_retention import independent_can


class ExpandedTests(unittest.TestCase):
    def test_matches_independent_exhaustive_byte_optimum(self):
        rng=random.Random(9083)
        for case in range(20):
            g=Graph(env={});ids=[];caps={}
            for i in range(7):
                deps=rng.sample(ids,min(len(ids),rng.randrange(3)))
                nid=g.add('test',deps,{'i':i},rng.randrange(5),i%3!=0,str(i),.01,case,mandatory=i==0)
                ids.append(nid)
                if g.nodes[nid].replayable:caps[nid]='group'+str(i%3)
            g.targets={'0':ids[-2:]};groups=sorted(set(caps.values()));k=1
            faults=[set(),*({c} for c in groups)];optional=sorted(g.candidates-g.roots)
            possible=[g.roots|{b for b,f in zip(optional,flags) if f}
                for flags in itertools.product((False,True),repeat=len(optional))]
            optimum=min(retained_bytes(g,s,caps,k) for s in possible
                if all(independent_can(g,s,caps,f) for f in faults))
            for solver in (expanded,optimize):
                selected,status,diag=solver(g,caps,k)
                self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
                self.assertEqual(retained_bytes(g,selected,caps,k),optimum)

    def test_size_guard_never_certifies_a_skipped_problem(self):
        g=Graph(env={});nid=g.add('test',[],{},1,True,'x',0,0);g.targets={'0':[nid]}
        _,status,diag=expanded(g,{nid:'x'},1,maximum_scenarios=1)
        self.assertEqual(status,'scenario_limit');self.assertFalse(diag['robust_certified'])
