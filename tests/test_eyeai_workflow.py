import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from threadpoolctl import threadpool_limits

from recoverml.core import Graph, RestoreError, digest, pack, write_store
from recoverml.eyeai_workflow import capture, execute, implementation_sha256
from recoverml.witness import WitnessRestorer


class EyeAIWorkflowTests(unittest.TestCase):
    def test_actual_feature_revision_and_missing_entrypoint_guard(self):
        module = importlib.import_module('recoverml.eyeai_workflow')
        images = np.random.default_rng(7).integers(0, 256, (2, 16, 16, 3), dtype=np.uint8)
        values = []
        for revision, entrypoint in [('aligned', 'eyeai_current'), ('legacy_shift3', 'eyeai_legacy')]:
            params = dict(revision=revision, implementation_sha256=implementation_sha256(),
                entrypoint_sha256=digest(Path(module.__file__).with_name(entrypoint + '.py').read_bytes()),
                shared_feature_sha256=digest(Path(module.__file__).with_name('eyeai_current.py').read_bytes()))
            values.append(execute('retina_features', [images], params))
        self.assertFalse(np.array_equal(*values))
        with patch.object(Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(RestoreError, 'Retired'):
                execute('retina_features', [images], params)

    @unittest.skipUnless(Path('work/stare/stare-images').is_dir(), 'STARE acquisition required')
    def test_real_data_root_replay_both_processing_revisions(self):
        with threadpool_limits(limits=1), tempfile.TemporaryDirectory() as tmp:
            graph, info = capture('work/stare', 'forest', 3, 2, image_size=32, training_pixels=500)
            self.assertEqual(len(info['train_images']), 15)
            self.assertFalse(set(info['train_images']) & set(info['test_images']))
            store = Path(tmp) / 'store'
            write_store(graph, graph.roots, store)
            disk = Graph.read(store / 'manifest.json')
            for version in graph.targets:
                values = WitnessRestorer(disk, store, replay_execute=execute).version(version)
                for node, value in zip(graph.targets[version], values):
                    self.assertEqual(digest(pack(value)), graph.nodes[node].blob)


if __name__ == '__main__':
    unittest.main()
