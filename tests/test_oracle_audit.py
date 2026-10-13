import unittest
from recoverml.oracle_audit import graph,reference
from recoverml.topology_scaling import build_wide_history
from recoverml.optimizer import optimize


class OracleAuditTests(unittest.TestCase):
    def test_independent_cost_matches_executor_model_with_aliases(self):
        g=graph(17001)
        for kept in (g.roots,g.candidates,g.roots|{g.nodes[t].blob
                           for ts in g.targets.values() for t in ts}):
            self.assertEqual(reference(g,kept),g.estimate(kept))

    def test_no_boundary_control_keeps_all_live_ancestors(self):
        g=build_wide_history(4,5,2,901,boundary_mode='none')
        budget=g.size(g.candidates)
        _,s2,h2=optimize(g,budget)
        _,s3,h3=optimize(g,budget,prune_opaque=True)
        self.assertEqual(s2,s3)
        self.assertEqual(h2[0]['variables'],h3[0]['variables'])

    def test_mixed_frontier_preserves_live_shared_ancestry(self):
        g=build_wide_history(4,5,2,901,boundary_mode='mixed')
        budget=g.size(g.candidates)
        k2,s2,h2=optimize(g,budget)
        k4,s4,h4=optimize(g,budget,prune_opaque=True,compact=True)
        self.assertEqual(s2,s4);self.assertEqual(s2,'ok')
        self.assertAlmostEqual(reference(g,k2),reference(g,k4),places=9)
        self.assertLess(h4[0]['variables'],h2[0]['variables'])
