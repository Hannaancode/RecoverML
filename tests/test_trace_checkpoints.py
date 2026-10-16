import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('shared_followup_runner',
    Path(__file__).resolve().parents[1]/'scripts/run_multiview_shared_followup.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TraceCheckpointTests(unittest.TestCase):
    def test_closed_members_remain_readable_and_append_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'trace.jsonl.gz'
            with runner.CheckpointTrace(path) as trace:
                trace.write('{"history":1}\n');trace.checkpoint()
                prefix=path.read_bytes()
                self.assertEqual(gzip.decompress(prefix),b'{"history":1}\n')
                trace.write('{"history":2}\n');trace.checkpoint()
                self.assertTrue(path.read_bytes().startswith(prefix))
                self.assertEqual(gzip.decompress(path.read_bytes()),b'{"history":1}\n{"history":2}\n')

    def test_exception_closes_active_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'trace.jsonl.gz'
            with self.assertRaises(RuntimeError):
                with runner.CheckpointTrace(path) as trace:
                    trace.write('{"history":1}\n')
                    raise RuntimeError('interruption')
            self.assertEqual(gzip.decompress(path.read_bytes()),b'{"history":1}\n')
