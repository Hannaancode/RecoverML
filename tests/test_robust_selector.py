import unittest
from unittest.mock import patch
from recoverml.core import Graph
from recoverml.robust_retention import optimize


class SelectorTests(unittest.TestCase):
    def test_selector_preserves_unknown_status_instead_of_claiming_success(self):
        graph=Graph(env={})
        with patch('recoverml.robust_retention.expanded',return_value=(set(),'no_incumbent',dict(storage_optimal=False,robust_certified=False))):
            _,status,diag=optimize(graph,{},0)
        self.assertEqual(status,'no_incumbent');self.assertFalse(diag['robust_certified'])

    def test_small_real_case_matches_independent_byte_answer(self):
        graph=Graph(env={});nid=graph.add('external',[],{},7,False,'x',0,0);graph.targets={'0':[nid]}
        chosen,status,diag=optimize(graph,{},0)
        self.assertEqual(status,'ok');self.assertEqual(chosen,{graph.nodes[nid].blob})
        self.assertEqual(diag['selected_engine'],'expanded_exact')
