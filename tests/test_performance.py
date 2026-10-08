"""End-to-end checks for complete restore evidence and rejection of altered logs."""
import csv
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from recoverml.benchmark import write_csv
from recoverml.performance import run, audit


class PerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        root = Path(cls.fixture.name)
        config = root/'config.json'
        config.write_text(json.dumps(dict(rows=[80],workers=[1,2],
            policies=['full_replay','recoverability_v2'],versions=2,requests=4,repeats=1)))
        cls.original = root/'original'
        cls.report = run(config,cls.original)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name)/'results'
        shutil.copytree(self.original,self.out)

    def refresh_hash(self, name):
        path = self.out/'HASHES.json'
        hashes = json.loads(path.read_text())
        hashes[name] = hashlib.sha256((self.out/name).read_bytes()).hexdigest()
        path.write_text(json.dumps(hashes))

    def remove_request_operations(self):
        with gzip.open(self.out/'operations.jsonl.gz','rt') as stream:
            operations = [json.loads(line) for line in stream]
        first = operations[0]
        with gzip.open(self.out/'operations.jsonl.gz','wt') as stream:
            for op in operations:
                if (op['trial'],op['request_id']) != (first['trial'],first['request_id']):
                    stream.write(json.dumps(op)+'\n')
        self.refresh_hash('operations.jsonl.gz')

    def test_parallel_restore(self):
        self.assertEqual(self.report['requests'],16)
        self.assertEqual(self.report['exact_requests'],16)
        self.assertTrue((self.out/'RUN_COMPLETE').exists())
        self.assertTrue(audit(self.out)['passed'])

    def test_missing_request_operations_with_refreshed_hash(self):
        self.remove_request_operations()
        with self.assertRaisesRegex(ValueError,'missing target operations'):
            audit(self.out)

    def test_changed_latency_with_refreshed_hash(self):
        with (self.out/'requests.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        rows[0]['service_ms'] = str(float(rows[0]['service_ms'])+1)
        write_csv(self.out/'requests.csv',rows)
        self.refresh_hash('requests.csv')
        with self.assertRaisesRegex(ValueError,'Latency mismatch'):
            audit(self.out)

    def test_missing_declared_trial_with_refreshed_hash(self):
        with (self.out/'summary.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        write_csv(self.out/'summary.csv',rows[1:])
        self.refresh_hash('summary.csv')
        with self.assertRaisesRegex(ValueError,'declared trial matrix'):
            audit(self.out)

    def test_changed_file_hash(self):
        with gzip.open(self.out/'operations.jsonl.gz','at') as stream:
            stream.write('{}\n')
        with self.assertRaisesRegex(ValueError,'File hash mismatch'):
            audit(self.out)

    def test_optimized_python_still_rejects_incomplete_trace(self):
        self.remove_request_operations()
        result = subprocess.run([sys.executable,'-O','-m','recoverml.performance',
                                 '--audit-only','--out',str(self.out)],
                                capture_output=True,text=True,env=os.environ.copy())
        self.assertNotEqual(result.returncode,0)
        self.assertIn('missing target operations',result.stderr)
