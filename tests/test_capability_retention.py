import itertools
import random
import tempfile
import unittest
from pathlib import Path
from recoverml.core import Graph,pack,write_store
from recoverml.capability_retention import counterexample,optimize,retained_bytes,CapabilityRestorer


def independent_can(graph,retained,capabilities,disabled):
    producers={}
    for n in graph.nodes.values():
        if n.replayable and capabilities.get(n.id) not in disabled:
            producers.setdefault(n.blob,[]).append(n)
    def visit(blob,path):
        if blob in retained: return True
        if blob in path: return False
        return any(all(visit(graph.nodes[d].blob,path|{blob}) for d in n.deps)
                   for n in producers.get(blob,[]))
    return all(visit(graph.nodes[t].blob,set()) for ts in graph.targets.values() for t in ts)


class CapabilityTests(unittest.TestCase):
    def test_separation_and_robust_optimum_against_exhaustive_oracle(self):
        rng=random.Random(508)
        for case in range(24):
            g=Graph(env={});ids=[];caps={}
            for i in range(7):
                deps=rng.sample(ids,min(len(ids),rng.randrange(3)))
                nid=g.add('test',deps,{'i':i},rng.randrange(4),rng.choice([True,False]),str(i),.01,case,mandatory=i==0)
                ids.append(nid)
                if g.nodes[nid].replayable and i%3: caps[nid]='provider'+str(i%3)
            g.targets={'0':ids[-2:]}
            groups=sorted(set(caps.values()));k=min(1,len(groups))
            faults=[set(f) for count in range(k+1) for f in itertools.combinations(groups,count)]
            optional=sorted(g.candidates-g.roots);best=float('inf');valid_sets=[]
            for flags in itertools.product([False,True],repeat=len(optional)):
                retained=g.roots|{b for b,flag in zip(optional,flags) if flag}
                expected=all(independent_can(g,retained,caps,f) for f in faults)
                result=counterexample(g,retained,caps,k)
                self.assertEqual(result['status']=='certified',expected)
                if expected:
                    valid_sets.append(retained)
                    best=min(best,retained_bytes(g,retained,caps,k))
                elif result['status']=='counterexample':
                    # The returned cut must reject this set and be necessary
                    # for every truly robust candidate, checked below.
                    self.assertFalse(set(result['storage_cut'])&retained)
            for flags in itertools.product([False,True],repeat=len(optional)):
                retained=g.roots|{b for b,flag in zip(optional,flags) if flag}
                result=counterexample(g,retained,caps,k)
                if result['status']=='counterexample':
                    self.assertTrue(all(set(result['storage_cut'])&s for s in valid_sets))
            selected,status,diag=optimize(g,caps,k)
            self.assertEqual(status,'ok');self.assertTrue(diag['robust_certified'])
            self.assertEqual(retained_bytes(g,selected,caps,k),best)
            self.assertEqual(optimize(g,caps,k,budget=best-1)[1],'proven_infeasible')

    def test_correlated_group_losses_and_alias_cycles(self):
        g=Graph(env={})
        root=g.add('input',[],{},1,False,'root',0.,0,mandatory=True)
        target=g.add('external',[],{},2,False,'external',0.,0)
        a=g.add('affine_features',[root],dict(scale=1,offset=1),2,True,'providerA',.01,0)
        b=g.add('affine_features',[root],dict(scale=2,offset=0),2,True,'providerB',.01,0)
        cycle=g.add('affine_features',[target],dict(scale=1,offset=0),2,True,'cycle',.01,0)
        g.targets={'0':[target]};caps={a:'A',b:'B',cycle:'cycle'}
        self.assertEqual(counterexample(g,g.roots,caps,1)['status'],'certified')
        failure=counterexample(g,g.roots,caps,2)
        self.assertEqual(set(failure['disabled']),{'A','B'})
        selected,status,_=optimize(g,caps,2)
        self.assertEqual(selected,g.roots|{g.nodes[target].blob});self.assertEqual(status,'ok')
        # Same failure label disables both different logical producers.
        self.assertEqual(counterexample(g,g.roots,{a:'shared',b:'shared',cycle:'cycle'},1)['disabled'],['shared'])

    def test_actual_disk_recovery_uses_surviving_producer(self):
        import numpy as np
        from recoverml.operators import execute
        g=Graph(env={});x=np.arange(8,dtype=float)
        root=g.add('input',[],{},x,False,'root',0.,0,mandatory=True)
        value=execute('affine_features',[x],dict(scale=2.,offset=1.))
        target=g.add('external',[],{},value,False,'external',0.,0)
        a=g.add('affine_features',[root],dict(scale=2.,offset=1.),value,True,'A',.01,0)
        b=g.add('affine_features',[root],dict(scale=2.,offset=1.),value,True,'B',.01,0)
        g.targets={'0':[target]}
        with tempfile.TemporaryDirectory() as temp:
            store=Path(temp)/'store';write_store(g,g.roots,store)
            disk=Graph.read(store/'manifest.json')
            restorer=CapabilityRestorer(disk,store,{a:'A',b:'B'},['A'],verify_environment=False)
            self.assertEqual(pack(restorer.get(target)),g.archive[g.nodes[target].blob])
            self.assertEqual(restorer.trace[-1]['producer'],b)
            self.assertEqual(disk.archive,{})

    def test_iteration_limit_is_never_called_robust(self):
        g=Graph(env={});target=g.add('external',[],{},7,False,'external',0.,0)
        g.targets={'0':[target]}
        _,status,diag=optimize(g,{},0,max_iterations=1)
        self.assertEqual(status,'iteration_limit');self.assertFalse(diag['robust_certified'])
