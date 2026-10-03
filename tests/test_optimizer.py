import unittest
from unittest.mock import patch
import numpy as np
from recoverml.core import Graph
from recoverml.policies import select, exact
from recoverml.optimizer import optimize


def small_graph(seed):
    rng = np.random.default_rng(seed)
    g = Graph()
    root = g.add('input',[],{},np.arange(8),False,'source',0.,0,True)
    nodes = [root]
    for i in range(7):
        parents = [nodes[j] for j in rng.choice(len(nodes),size=min(2,len(nodes)),replace=False)]
        node = g.add('fixture',parents,{'i':i},np.zeros(8*(i+1))+i,
                     i not in (0,3),'fixture',float(rng.uniform(1e-6,.003)),0)
        nodes.append(node)
    g.targets = {'0':[nodes[-1],nodes[-2]],'1':[nodes[-3],nodes[-1]]}
    return g


class OptimizerTests(unittest.TestCase):
    def test_milp_matches_exhaustive_on_shared_opaque_graphs(self):
        for seed in range(8):
            g = small_graph(seed)
            minimum = exact(g)['objective']
            for budget in (minimum-1,minimum,int((minimum+g.size(g.candidates))/2),g.size(g.candidates)):
                oracle = exact(g,budget)
                retained,status,history = optimize(g,budget,time_limit_s=5.)
                with self.subTest(seed=seed,budget=budget):
                    self.assertEqual(status=='ok',oracle['feasible'])
                    if oracle['feasible']:
                        self.assertLessEqual(g.size(retained),budget)
                        self.assertTrue(g.coverage(retained)[0])
                        self.assertAlmostEqual(g.estimate(retained),oracle['objective'],places=9)
                        self.assertTrue(history[0]['estimated_optimal'])
                    else:
                        self.assertEqual(status,'proven_infeasible')

    def test_direct_target_lower_bound_avoids_solver(self):
        g = small_graph(18)
        for n in g.nodes.values():
            n.compute_s = .01
        with patch('scipy.optimize.milp',side_effect=AssertionError('unneeded solver')):
            s,status,history = optimize(g,g.size(g.candidates))
        self.assertEqual(status,'ok')
        self.assertEqual(history[0]['strategy'],'direct_target_lower_bound')
        self.assertAlmostEqual(g.estimate(s),history[0]['estimated_cost_s'])

    def test_solver_failure_uses_validated_heuristic(self):
        g = small_graph(9)
        with patch('recoverml.optimizer.optimize',return_value=(set(g.roots),'solver_no_incumbent',[])):
            selected = select(g,'recoverability_v2',g.size(g.candidates))
        self.assertEqual(selected.status,'ok')
        self.assertTrue(g.coverage(selected.retained)[0])
        self.assertEqual(selected.history[-1]['strategy'],'heuristic_fallback')

    def test_cheap_target_replay_does_not_get_false_lower_bound(self):
        g = small_graph(10)
        for ts in g.targets.values():
            for tid in ts:
                g.nodes[tid].compute_s = 0.
        s,status,history = optimize(g,g.size(g.candidates),time_limit_s=5.)
        self.assertEqual(history[0]['strategy'],'bounded_global_milp')
        oracle = exact(g,g.size(g.candidates))
        self.assertEqual(status,'ok')
        self.assertAlmostEqual(g.estimate(s),oracle['objective'],places=9)

    def test_bounded_incumbent_is_not_called_optimal(self):
        from scipy.optimize import milp
        g = small_graph(10)
        for ts in g.targets.values():
            for tid in ts:
                g.nodes[tid].compute_s = 0.
        def limited(*args,**kwargs):
            result = milp(*args,**kwargs)
            result.status = 1
            result.message = 'Test: feasible incumbent at time limit'
            return result
        with patch('scipy.optimize.milp',side_effect=limited):
            retained,status,history = optimize(g,g.size(g.candidates))
        self.assertEqual(status,'ok')
        self.assertTrue(g.coverage(retained)[0])
        self.assertFalse(history[0]['estimated_optimal'])

    def test_mismatched_solver_objective_is_rejected(self):
        from scipy.optimize import milp
        g = small_graph(10)
        for ts in g.targets.values():
            for tid in ts:
                g.nodes[tid].compute_s = 0.
        def wrong(*args,**kwargs):
            result = milp(*args,**kwargs)
            result.fun += 1e6
            return result
        with patch('scipy.optimize.milp',side_effect=wrong):
            _,status,history = optimize(g,g.size(g.candidates))
        self.assertEqual(status,'solver_incumbent_rejected')
        self.assertFalse(history[0]['postchecked'])

    def test_shared_blob_and_overlapping_targets_match_oracle(self):
        g = small_graph(10)
        parents = g.targets['0']
        value = np.ones(32)
        a = g.add('fixture',parents,{'branch':1},value,True,'fixture',0.,0)
        b = g.add('fixture',parents,{'branch':2},value,True,'fixture',0.,0)
        self.assertNotEqual(a,b)
        self.assertEqual(g.nodes[a].blob,g.nodes[b].blob)
        g.targets = {'0':[parents[0],a,a,b],'1':[a,b]}
        budget = g.size(g.candidates)
        s,status,_ = optimize(g,budget,time_limit_s=5.)
        self.assertEqual(status,'ok')
        self.assertAlmostEqual(g.estimate(s),exact(g,budget)['objective'],places=9)


if __name__=='__main__':
    unittest.main()
