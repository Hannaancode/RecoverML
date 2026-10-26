import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_planner_efficiency import identities
from benchmark_planner_efficiency import stress
from recoverml.capability_retention import retained_bytes
from recoverml.component_retention import optimize


class PlannerFollowupTests(unittest.TestCase):
    def test_missing_duplicate_and_replaced_timings_are_rejected(self):
        records=[dict(case='a',method=m,repetition=r) for m in ('new','old') for r in range(3)]
        identities(records,['a'],['new','old'],3)
        for bad in (records[:-1],records+[records[0]],[dict(x,case='b') for x in records]):
            with self.assertRaises(ValueError):
                identities(bad,['a'],['new','old'],3)

    def test_both_scaling_topologies_match_analytic_optimum_without_payloads(self):
        for topology in ('independent_branches','wide_frontier'):
            g,caps,k,expected=stress(topology,16,101)
            self.assertFalse(g.archive)
            chosen,status,diag=optimize(g,caps,k)
            self.assertEqual(status,'ok')
            self.assertTrue(diag['storage_optimal'])
            self.assertEqual(retained_bytes(g,chosen,caps,k),expected)
