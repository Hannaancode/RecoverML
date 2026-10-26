"""Both native workers must recover exact files without a captured oracle."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from threadpoolctl import threadpool_limits
from recoverml.core import RestoreError, digest, write_store
from recoverml.multiview_workflow import capture

SPEC = importlib.util.spec_from_file_location('native_worker', Path(__file__).resolve().parents[1] / 'scripts/native_frontier_worker.py')
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class NativeFrontierTests(unittest.TestCase):
    def test_retained_native_cache_is_a_hard_link_and_extra_objects_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / 'store'
            blobs = store / 'blobs'
            blobs.mkdir(parents=True)
            raw = b'paid retained bytes'
            blob = digest(raw)
            source = blobs / (blob + '.pkl')
            source.write_bytes(raw)
            cache = store / '.dvc/cache'
            cache.mkdir(parents=True)
            (cache / 'unpaid').write_bytes(b'hidden downstream output')
            (cache / 'unpaid').chmod(0o400)
            hashes = worker.reset_selected_cache(cache, blobs, {'files/md5/aa/object': blob})
            self.assertEqual(hashes, [blob])
            self.assertFalse((cache / 'unpaid').exists())
            self.assertTrue(source.samefile(cache / 'files/md5/aa/object'))
            with self.assertRaises(ValueError):
                worker.reset_selected_cache(Path(temporary) / 'outside', blobs, {})

    def test_both_backends_restore_all_exact_target_files_from_features(self):
        with threadpool_limits(limits=1):
            graph, _, _ = capture('wine', 20261016, 4, False)
            selected = graph.roots | {n.blob for n in graph.nodes.values() if n.op == 'view_standardize'}
            for backend in ('recoverml', 'dvc_batch'):
                with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / 'store'
                    write_store(graph, selected, path)
                    report = worker.recover(backend, path)
                    self.assertEqual(report['status'], 'PASS')
                    for targets in graph.targets.values():
                        for target in targets:
                            blob = graph.nodes[target].blob
                            self.assertEqual((path / 'outputs' / (blob + '.pkl')).read_bytes(), graph.archive[blob])

    def test_missing_retired_view_cannot_be_silently_recomputed(self):
        with threadpool_limits(limits=1):
            graph, _, _ = capture('wine', 20261016, 4, False)
            selected = graph.roots | {n.blob for n in graph.nodes.values() if n.op == 'view_standardize'}
            for backend in ('recoverml', 'dvc_batch'):
                with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / 'store'
                    write_store(graph, selected, path)
                    missing = next(n.blob for n in graph.nodes.values() if n.op == 'view_standardize')
                    (path / 'blobs' / (missing + '.pkl')).unlink()
                    with self.assertRaises(RestoreError):
                        worker.recover(backend, path)


if __name__ == '__main__':
    unittest.main()
