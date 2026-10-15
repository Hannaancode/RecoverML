"""Adversarial checks of failure handling and executable witness correctness.

Mocked solver responses exercise status handling reproducibly; they are not
evidence of solver speed or failures observed in production HiGHS runs.
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from recoverml.core import Graph, RestoreError, pack, write_store
from recoverml.operators import execute
from recoverml.witness import WitnessRestorer, certificate
from recoverml.capability_retention import (
    counterexample, optimize as separated, retained_bytes,
)
from recoverml.scenario_retention import optimize as expanded
from recoverml.component_retention import optimize as decomposed


def opaque_graph():
    graph = Graph(env={})
    target = graph.add('external_features', [], {}, np.array([7.]), False,
                       'opaque', 0., 0)
    graph.targets = {'0': [target]}
    return graph, target


class ScientificNegativeTests(unittest.TestCase):
    def test_master_timeout_without_incumbent_is_unknown(self):
        graph, _ = opaque_graph()
        result = SimpleNamespace(status=1, x=None, fun=None, message='Time limit reached')
        with patch('recoverml.capability_retention.solve', return_value=result):
            _, status, diagnostic = separated(graph, {}, 0)
        self.assertEqual(status, 'master_unknown')
        self.assertFalse(diagnostic['robust_certified'])
        self.assertFalse(diagnostic['storage_optimal'])

    def test_oracle_timeout_without_incumbent_is_unknown(self):
        graph, _ = opaque_graph()
        result = SimpleNamespace(status=1, x=None, fun=None, message='Time limit reached')
        with patch('recoverml.capability_retention.solve', return_value=result):
            diagnostic = counterexample(graph, set(), {}, 0)
        self.assertEqual(diagnostic['status'], 'unknown')

    def test_feasible_timed_out_oracle_can_supply_a_cut_but_not_minimum_failure_proof(self):
        graph, _ = opaque_graph()
        result = SimpleNamespace(status=1, x=np.zeros(1), fun=0., message='Time limit reached')
        with patch('recoverml.capability_retention.solve', return_value=result):
            diagnostic = counterexample(graph, set(), {}, 0)
        self.assertEqual(diagnostic['status'], 'counterexample')
        self.assertTrue(diagnostic['postchecked'])
        self.assertFalse(diagnostic['minimum_failure_proved'])
        self.assertEqual(set(diagnostic['storage_cut']), graph.candidates)

    def test_oracle_unknown_is_not_promoted_to_robustness(self):
        graph, _ = opaque_graph()
        master = SimpleNamespace(status=0, x=np.zeros(1), fun=0., message='Optimal')
        unknown = SimpleNamespace(status=1, x=None, fun=None, message='Time limit reached')
        with patch('recoverml.capability_retention.solve', side_effect=[master, unknown]):
            _, status, diagnostic = separated(graph, {}, 0)
        self.assertEqual(status, 'oracle_unknown')
        self.assertFalse(diagnostic['robust_certified'])
        self.assertFalse(diagnostic['storage_optimal'])

    def test_inconsistent_master_objective_is_rejected(self):
        graph, _ = opaque_graph()
        inconsistent = SimpleNamespace(status=0, x=np.ones(1), fun=0., message='Mock optimal')
        with patch('recoverml.capability_retention.solve', return_value=inconsistent), \
             patch('recoverml.capability_retention.counterexample', return_value={'status': 'certified'}):
            _, status, diagnostic = separated(graph, {}, 0)
        self.assertEqual(status, 'master_rejected')
        self.assertFalse(diagnostic['storage_optimal'])

    def test_nonfinite_and_fractional_master_values_are_rejected(self):
        graph, _ = opaque_graph()
        for value in (float('nan'), float('inf'), .25, 2.):
            inconsistent = SimpleNamespace(status=0, x=np.array([value]), fun=0., message='Mock optimal')
            with self.subTest(value=value), \
                 patch('recoverml.capability_retention.solve', return_value=inconsistent):
                _, status, diagnostic = separated(graph, {}, 0)
            self.assertEqual(status, 'master_rejected')
            self.assertFalse(diagnostic['robust_certified'])
            self.assertFalse(diagnostic['storage_optimal'])

    def test_master_must_satisfy_previously_generated_storage_cuts(self):
        graph, _ = opaque_graph()
        inconsistent = SimpleNamespace(status=0, x=np.zeros(1), fun=0., message='Mock optimal')
        cut = {'status': 'counterexample', 'storage_cut': sorted(graph.candidates)}
        with patch('recoverml.capability_retention.solve', return_value=inconsistent), \
             patch('recoverml.capability_retention.counterexample', return_value=cut) as oracle:
            _, status, diagnostic = separated(graph, {}, 0)
        self.assertEqual(status, 'master_rejected')
        self.assertFalse(diagnostic['storage_optimal'])
        self.assertEqual(oracle.call_count, 1)

    def test_expanded_timeout_without_incumbent_is_not_certified(self):
        graph, _ = opaque_graph()
        result = SimpleNamespace(status=1, x=None, fun=None, message='Time limit reached')
        with patch('scipy.optimize.milp', return_value=result):
            _, status, diagnostic = expanded(graph, {}, 0)
        self.assertEqual(status, 'no_incumbent')
        self.assertFalse(diagnostic['robust_certified'])
        self.assertFalse(diagnostic['storage_optimal'])

    def test_expanded_feasible_timeout_is_not_called_optimal(self):
        graph, _ = opaque_graph()
        def timed_out(cost, **kwargs):
            return SimpleNamespace(status=1, x=np.ones(len(cost)), fun=float(cost.sum()),
                                   message='Time limit reached')
        with patch('scipy.optimize.milp', side_effect=timed_out):
            _, status, diagnostic = expanded(graph, {}, 0)
        self.assertEqual(status, 'uncertified_optimum')
        self.assertTrue(diagnostic['robust_certified'])
        self.assertFalse(diagnostic['storage_optimal'])

    def test_two_blob_alias_cycle_needs_a_grounded_stored_source(self):
        graph = Graph(env={})
        original = graph.add('external_features', [], {}, np.array([1.]), False, 'a', 0., 0)
        second = graph.add('test', [original], {}, np.array([2.]), True, 'b', .01, 0)
        graph.add('test', [second], {}, np.array([1.]), True, 'alternate_a', .01, 0)
        graph.targets = {'0': [second]}
        self.assertFalse(certificate(graph, set())['complete'])
        expected = min(retained_bytes(graph, {b}, {}, 0) for b in graph.candidates)
        for solver in (separated, expanded, decomposed):
            selected, status, diagnostic = solver(graph, {}, 0)
            self.assertEqual(status, 'ok')
            self.assertTrue(diagnostic['storage_optimal'])
            self.assertEqual(retained_bytes(graph, selected, {}, 0), expected)
            self.assertTrue(certificate(graph, selected)['complete'])

    def test_unstored_opaque_target_fails_without_using_capture_archive(self):
        graph, target = opaque_graph()
        self.assertTrue(graph.archive)  # It must not become a restore source.
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'
            write_store(graph, set(), store)
            with self.assertRaisesRegex(RestoreError, 'No grounded'):
                WitnessRestorer(graph, store, verify_environment=False).get(target)

    def test_file_deleted_after_certificate_fails_closed(self):
        graph, target = opaque_graph()
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'
            write_store(graph, graph.candidates, store)
            restorer = WitnessRestorer(graph, store, verify_environment=False)
            (store / 'blobs' / (graph.nodes[target].blob + '.pkl')).unlink()
            with self.assertRaisesRegex(RestoreError, 'Cannot read retained'):
                restorer.get(target)
            self.assertEqual(restorer.trace, [])

    def test_corrupt_retained_file_is_not_bypassed_by_alternate_replay(self):
        graph = Graph(env={})
        value = np.array([1.])
        root = graph.add('input', [], {}, value, False, 'source', 0., 0, mandatory=True)
        params = {'scale': 2., 'offset': 0.}
        output = execute('affine_features', [value], params)
        target = graph.add('affine_features', [root], params, output, True, 'live', .01, 0)
        graph.targets = {'0': [target]}
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'
            write_store(graph, graph.candidates, store)
            (store / 'blobs' / (graph.nodes[target].blob + '.pkl')).write_bytes(b'corrupt')
            restorer = WitnessRestorer(graph, store, verify_environment=False)
            with self.assertRaisesRegex(RestoreError, 'Corrupt retained'):
                restorer.get(target)
            self.assertEqual(restorer.trace, [])

    def test_environment_drift_is_rejected_before_execution(self):
        graph, _ = opaque_graph()
        with patch('recoverml.core.environment', return_value={'numpy': 'changed'}):
            with self.assertRaisesRegex(RestoreError, 'environment/operator code mismatch'):
                WitnessRestorer(graph, Path('/unused'))

    def test_undeclared_nondeterminism_is_detected_by_output_hash(self):
        graph = Graph(env={})
        source = graph.add('input', [], {}, np.array([1.]), False, 'source', 0., 0, mandatory=True)
        params = {'scale': 2., 'offset': 0.}
        target = graph.add('affine_features', [source], params, np.array([2.]), True, 'assumed_pure', .01, 0)
        graph.targets = {'0': [target]}
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'
            write_store(graph, graph.roots, store)
            changing_replay = lambda *args: np.array([3.])
            restorer = WitnessRestorer(graph, store, verify_environment=False,
                                       replay_execute=changing_replay)
            with self.assertRaisesRegex(RestoreError, 'hash mismatch'):
                restorer.get(target)
            self.assertNotIn(graph.nodes[target].blob, restorer.memo)

    def test_deep_grounded_chain_recovers_without_python_recursion(self):
        graph = Graph(env={})
        value = np.array([0.])
        node = graph.add('input', [], {}, value, False, 'source', 0., 0, mandatory=True)
        for _ in range(2048):
            params = {'scale': 1., 'offset': 1.}
            value = execute('affine_features', [value], params)
            node = graph.add('affine_features', [node], params, value, True, 'chain', .001, 0)
        graph.targets = {'0': [node]}
        self.assertTrue(certificate(graph, graph.roots)['complete'])
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'
            write_store(graph, graph.roots, store)
            restorer = WitnessRestorer(graph, store, verify_environment=False)
            self.assertEqual(pack(restorer.get(node)), pack(value))
            self.assertEqual(len(restorer.trace), 2049)
            self.assertTrue(all(step['exact'] for step in restorer.trace))

    def test_dependency_order_and_shared_subgraph_execute_once(self):
        graph = Graph(env={})
        root_value = np.array([1.])
        root = graph.add('input', [], {}, root_value, False, 'source', 0., 0, mandatory=True)
        branches = []
        values = []
        for offset in (2., 4.):
            params = {'scale': 1., 'offset': offset}
            value = execute('affine_features', [root_value], params)
            branches.append(graph.add('affine_features', [root], params, value, True, 'branch', .01, 0))
            values.append(value)
        output = execute('mean_features', values, {})
        target = graph.add('mean_features', branches, {}, output, True, 'join', .01, 0)
        graph.targets = {'0': [target]}
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'
            write_store(graph, graph.roots, store)
            restorer = WitnessRestorer(graph, store, verify_environment=False)
            self.assertEqual(pack(restorer.get(target)), pack(output))
            self.assertEqual([e['requested_node'] for e in restorer.trace], [root, *branches, target])
            trace_length = len(restorer.trace)
            restorer.get(target)
            self.assertEqual(len(restorer.trace), trace_length)


if __name__ == '__main__':
    unittest.main()
