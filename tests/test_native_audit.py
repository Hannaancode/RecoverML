"""A constant request count must not hide a missing native comparison."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('native_audit', Path(__file__).resolve().parents[1] / 'scripts/audit_native_frontier.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class NativeAuditTests(unittest.TestCase):
    def test_duplicate_replacement_and_missing_requests_are_rejected(self):
        expected = {('h', 'RecoverML_native', 0), ('h', 'DVC_native_batch', 0)}
        records = [dict(history=h, method=m, repetition=r) for h, m, r in sorted(expected)]
        audit.identities(list(reversed(records)), expected)
        for changed in [records[:-1], records + [records[0]], records[:-1] + [records[0]]]:
            with self.subTest(records=changed), self.assertRaises(ValueError):
                audit.identities(changed, expected)


if __name__ == '__main__':
    unittest.main()
