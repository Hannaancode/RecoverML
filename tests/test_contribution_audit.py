"""Structural necessity checks must reject alias cycles and alternate producers."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('audit_contribution', Path(__file__).resolve().parents[1] / 'scripts/audit_contribution_evidence.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def manifest(nodes, roots=('root',)):
    return dict(nodes=[dict(id=nid, blob=blob, deps=deps, replayable=replayable)
                       for nid, blob, deps, replayable in nodes], mandatory_blobs=list(roots))


class ContributionAuditTests(unittest.TestCase):
    def test_and_dependency_is_eligible(self):
        data = manifest([('r', 'root', [], False), ('a', 'a', ['r'], True),
                         ('b', 'b', ['r'], True), ('t', 't', ['a', 'b'], True)])
        self.assertTrue(audit.classify(data)['sufficient_single_producer_dag'])

    def test_alternative_producers_fail_sufficient_uniqueness_condition(self):
        data = manifest([('r', 'root', [], False), ('a', 'target', ['r'], True),
                         ('b', 'target', ['r'], True)])
        self.assertFalse(audit.classify(data)['sufficient_single_producer_dag'])

    def test_ungrounded_cycle_is_not_an_easy_dag(self):
        data = manifest([('r', 'root', [], False), ('a', 'a', ['b'], True), ('b', 'b', ['a'], True)])
        self.assertFalse(audit.classify(data)['physical_dag_after_fixing_roots'])

    def test_mandatory_root_breaks_a_physical_cycle(self):
        data = manifest([('r', 'root', ['a'], True), ('a', 'a', ['r'], True)])
        self.assertTrue(audit.classify(data)['sufficient_single_producer_dag'])

    def test_duplicate_policy_condition_is_not_silently_overwritten(self):
        row = dict(case='one', policy='RecoverML_exact', retained_bytes='10')
        with self.assertRaises(ValueError):
            audit.comparison([row, dict(row)], ('case',))


if __name__ == '__main__':
    unittest.main()
