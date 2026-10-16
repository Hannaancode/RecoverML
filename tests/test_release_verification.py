"""Release checks must reject altered evidence without running captured models."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('verify_release', ROOT / 'scripts/verify_release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = release.Snapshot(ROOT)

    def snapshot(self):
        snapshot = copy.copy(self.original)
        snapshot.files = dict(self.original.files)
        return snapshot

    def test_missing_historical_archive_does_not_become_complete(self):
        snapshot = self.snapshot()
        snapshot.files.pop(release.SCIENTIFIC + '/captures.tar.gz', None)
        result = release.evidence_inventory(snapshot)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertIn(release.SCIENTIFIC + '/captures.tar.gz', result['missing'])

    def test_same_length_raw_tamper_fails_recorded_checksum(self):
        snapshot = self.snapshot()
        path = release.SCIENTIFIC + '/execution_traces.jsonl.gz'
        raw = bytearray(snapshot.files[path])
        raw[-1] ^= 1
        snapshot.files[path] = bytes(raw)
        self.assertIn(path, release.evidence_inventory(snapshot)['hash_mismatches'])

    def test_duplicate_scientific_request_at_fixed_count_is_rejected(self):
        snapshot = self.snapshot()
        path = release.SCIENTIFIC + '/execution_traces.jsonl.gz'
        rows = snapshot.raw(path)
        rows[1] = dict(rows[0])
        snapshot.files[path] = gzip.compress(b''.join(json.dumps(r).encode() + b'\n' for r in rows))
        result = release.scientific_audit(snapshot)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('Duplicate scientific raw request', result['errors'])

    def test_duplicate_retinal_request_at_fixed_count_is_rejected(self):
        snapshot = self.snapshot()
        path = release.RETINAL + '/raw.jsonl.gz'
        rows = snapshot.raw(path)
        rows[1] = dict(rows[0])
        snapshot.files[path] = gzip.compress(b''.join(json.dumps(r).encode() + b'\n' for r in rows))
        result = release.retinal_audit(snapshot)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('Duplicate retinal raw request', result['errors'])

    def test_frozen_source_tamper_is_rejected(self):
        snapshot = self.snapshot()
        source = snapshot.json(release.LARGE + '/source_snapshot_receipt.json')['sources'][0]['saved_path']
        snapshot.files[source] += b'\n'
        result = release.source_audit(snapshot)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn(source, result['errors'])

    def test_checksum_manifest_cannot_silently_omit_a_tracked_file(self):
        snapshot = self.snapshot()
        for name in release.CHECKSUM_FILES:
            manifest = {p: release.sha(data) for p, data in snapshot.files.items() if p not in release.CHECKSUM_FILES}
            omitted = next(iter(manifest))
            manifest.pop(omitted)
            snapshot.files[name] = json.dumps(manifest).encode()
            result = release.checksum_audit(snapshot)[name]
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn(omitted, result['unlisted'])


if __name__ == '__main__':
    unittest.main()
