import itertools
import random
import copy
import unittest
from recoverml.core import Graph
from recoverml.component_retention import optimize,components
from recoverml.capability_retention import retained_bytes
from test_capability_retention import independent_can


class ComponentTests(unittest.TestCase):
    def test_matches_exhaustive_optimum_with_shared_loss_labels(self):
        rng=random.Random(24104)
        for case in range(32):
            g=Graph(env={});ids=[];caps={}
            for i in range(8):
                deps=rng.sample(ids,min(len(ids),rng.randrange(3)))
                nid=g.add('test',deps,dict(i=i),rng.randrange(5),rng.choice([True,False]),str(i),.01,case,mandatory=i==0)
                ids.append(nid)
                if g.nodes[nid].replayable:caps[nid]='shared'+str(i%3)
            g.targets={'0':ids[-3:]};groups=sorted(set(caps.values()));k=2
            faults=[set(f) for count in range(min(k,len(groups))+1) for f in itertools.combinations(groups,count)]
            optional=sorted(g.candidates-g.roots);best=float('inf')
            for flags in itertools.product([False,True],repeat=len(optional)):
                s=g.roots|{b for b,f in zip(optional,flags) if f}
                if all(independent_can(g,s,caps,f) for f in faults):best=min(best,retained_bytes(g,s,caps,k))
            selected,status,diag=optimize(g,caps,k)
            self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
            self.assertEqual(retained_bytes(g,selected,caps,k),best)
            self.assertTrue(all(independent_can(g,selected,caps,f) for f in faults))

    def test_shared_optional_artifact_prevents_incorrect_per_target_split(self):
        g=Graph(env={});source=g.add('input',[],{},b'x'*48,False,'shared',0,0)
        a=g.add('produce',[source],{'which':0},b'a'*32,True,'a',0,0)
        b=g.add('produce',[source],{'which':1},b'b'*32,True,'b',0,0)
        g.targets={'0':[a],'1':[b]}
        self.assertEqual(len(components(g)),1)
        selected,status,_=optimize(g,{},0)
        self.assertEqual(status,'ok');self.assertEqual(selected,{g.nodes[source].blob})

    def test_self_alias_is_not_an_independent_root_provider(self):
        g=Graph(env={});root=g.add('input',[],{},0,False,'root',0,0,mandatory=True)
        target=g.add('external',[],{},1,False,'target',0,0)
        live=g.add('test',[root],{},1,True,'provider',0,0)
        loop=g.add('test',[target],{},1,True,'self',0,0)
        g.targets={'0':[target]}
        selected,status,_=optimize(g,{live:'one',loop:'other'},1)
        self.assertEqual(status,'ok');self.assertEqual(selected,g.roots|{g.nodes[target].blob})

    def test_indexed_projections_preserve_aliases_target_order_and_input(self):
        g=Graph(env={});root=g.add('input',[],{},'root',False,'',0,0,mandatory=True)
        a=g.add('external',[],{},'a',False,'',0,0)
        alias=g.add('unavailable',[root],{},'a',False,'',0,0)
        b=g.add('external',[],{},'b',False,'',0,0)
        x=g.add('test',[a,root],{},'x',True,'',0,0)
        y=g.add('test',[b,root],{},'y',True,'',0,0)
        g.targets={'later':[y,x,y],'earlier':[alias,x]}
        original=copy.deepcopy(g.manifest())
        selected,status,diag=optimize(g,{},0)
        self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
        self.assertEqual(g.manifest(),original)
        self.assertTrue(independent_can(g,selected,{},set()))
        optional=sorted(g.candidates-g.roots)
        best=min(retained_bytes(g,s,{},0) for flags in itertools.product((False,True),repeat=len(optional))
            for s in [g.roots|{b for b,f in zip(optional,flags) if f}]
            if independent_can(g,s,{},set()))
        self.assertEqual(retained_bytes(g,selected,{},0),best)
