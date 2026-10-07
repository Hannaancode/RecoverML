"""End-to-end coverage of parallel restore isolation and trace auditing."""
import json
import gzip
import tempfile
import unittest
from pathlib import Path
from recoverml.performance import run, audit


class PerformanceTest(unittest.TestCase):
    def test_parallel_restore_and_corrupt_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            cfg=root/'config.json'
            cfg.write_text(json.dumps(dict(rows=[80],workers=[1,2],
                policies=['full_replay','recoverability_v2'],versions=2,requests=4,repeats=1)))
            out=root/'results'
            report=run(cfg,out)
            self.assertEqual(report['requests'],16)
            self.assertEqual(report['exact_requests'],16)
            self.assertTrue((out/'RUN_COMPLETE').exists())
            with gzip.open(out/'operations.jsonl.gz','at') as stream:
                stream.write('{}\n')
            with self.assertRaises((AssertionError,KeyError)):
                audit(out)
