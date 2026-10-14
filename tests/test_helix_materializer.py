import unittest
from recoverml.core import Graph
from recoverml.helix_materializer import select

class HelixRuleTests(unittest.TestCase):
    def test_out_of_scope_and_diamond_cost(self):
        g=Graph(env={});r=g.add('input',[],{},'root',False,'root',0.,0,mandatory=True)
        a=g.add('a',[r],{},'a',True,'a',1.,0);b=g.add('b',[a],{},'b',True,'b',2.,0)
        c=g.add('c',[a],{},'c',True,'c',3.,0);d=g.add('d',[b,c],{},'d',True,'d',4.,0)
        kept,diag=select(g,g.nodes[a].size,1e9)
        self.assertEqual(kept,g.roots|{g.nodes[a].blob})
        self.assertEqual(next(x for x in diag['decisions'] if x['node']==a)['event'],3)
        self.assertEqual(next(x for x in diag['decisions'] if x['node']==d)['cumulative_s'],10.)
    def test_strict_benefit_and_shared_payload(self):
        g=Graph(env={});a=g.add('a',[],{},'alias',True,'a',2.,0);g.add('b',[],{},'alias',True,'b',2.,0)
        size=g.nodes[a].size
        self.assertEqual(select(g,size,size)[0],set())
        kept,diag=select(g,size,2*size)
        self.assertEqual(kept,{g.nodes[a].blob});self.assertEqual(len(diag['decisions']),1)
