import tempfile
import unittest
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from recoverml.core import Graph, RestoreError, pack, unpack, write_store
from recoverml.scientific_workflows import (
    WORKFLOWS, capture, caps_for, execute, implementation_sha256,
)
from recoverml.witness import WitnessRestorer


class ScientificWorkflowTests(unittest.TestCase):
    def test_fixed_public_recipes_restore_all_models_and_predictions_from_roots(self):
        # One version checks all four operator families. The benchmark separately
        # uses all three frozen configurations and reports every resulting case.
        with threadpool_limits(limits=1):
            for name in WORKFLOWS:
                with self.subTest(workflow=name), tempfile.TemporaryDirectory() as tmp:
                    graph, info = capture(name, 101, versions=1)
                    self.assertFalse(info['deliberately_equal_alternatives'])
                    self.assertTrue(info['native_prediction_check'])
                    self.assertTrue(info['training_partition_only_fit'])
                    self.assertEqual(len(graph.roots), 2)
                    self.assertEqual(info['train_rows'] + info['test_rows'], info['rows'])
                    self.assertTrue(np.isfinite(info['quality']).all())
                    store = Path(tmp) / 'store'
                    write_store(graph, graph.roots, store)
                    disk = Graph.read(store / 'manifest.json')
                    self.assertEqual(disk.archive, {})
                    restored = WitnessRestorer(disk, store, replay_execute=execute).version('0')
                    for target, value in zip(graph.targets['0'], restored):
                        self.assertEqual(pack(value), graph.archive[graph.nodes[target].blob])

    def test_correlation_maps_fit_and_transform_to_same_family(self):
        graph, info = capture('iris_union', 211, versions=1)
        pre = caps_for(graph, 'preprocessing')
        broad = caps_for(graph, 'broad')
        self.assertEqual(set(pre.values()), {'preprocess:pca', 'preprocess:select_f',
                                           'preprocess:feature_union', 'split_membership'})
        self.assertEqual(set(broad.values()) - set(pre.values()), {'model_training', 'prediction'})
        self.assertEqual(set(broad), {n.id for n in graph.nodes.values() if n.replayable})
        for family in ('pca', 'select_f'):
            nodes = [n for n in graph.nodes.values() if n.params.get('estimator') == family]
            self.assertEqual(len(nodes), 2)
            self.assertEqual({pre[n.id] for n in nodes}, {'preprocess:' + family})
        self.assertEqual(info['transformed_columns'], 3)

    def test_transformer_fits_training_partition_and_loaded_state_replays(self):
        code = implementation_sha256()
        x = np.asarray([[0., 0.], [2., 2.], [1000., 1000.]])
        y = np.asarray([0, 1, 1])
        split = (np.asarray([0, 1]), np.asarray([2]))
        params = dict(implementation_sha256=code, estimator='standard', parameters={})
        state = execute('scientific_fit_transformer', [x, y, split], params)
        self.assertTrue(np.array_equal(state['fitted_state']['mean_'], np.asarray([1., 1.])))
        transformed = execute('scientific_transform', [x, unpack(pack(state))], params)
        self.assertTrue(np.array_equal(transformed[2], np.asarray([999., 999.])))

    def test_implementation_contract_and_fixed_version_range_are_enforced(self):
        with self.assertRaisesRegex(RestoreError, 'implementation contract'):
            execute('scientific_union', [], {'implementation_sha256': 'wrong'})
        for invalid in (0, 4, True):
            with self.assertRaises(ValueError):
                capture('iris_union', 101, invalid)
        with self.assertRaises(ValueError):
            capture('unknown', 101)
        with self.assertRaises(ValueError):
            caps_for(Graph(env={}), 'unknown')


if __name__ == '__main__':
    unittest.main()
