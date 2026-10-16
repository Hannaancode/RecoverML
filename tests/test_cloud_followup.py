"""Reject incomplete grids and incorrect shared-execution attribution."""
import copy
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('audit_cloud_followup', SCRIPTS / 'audit_cloud_followup.py')
cloud = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cloud)


class CloudFollowupTests(unittest.TestCase):
    def test_frozen_grid_rejects_missing_controls_and_method_replacement(self):
        config = dict(seeds=[20261016], datasets=['wine', 'breast_cancer'], versions=[4, 16, 64],
                      concat_materialized=[False, True], methods=sorted(cloud.METHODS),
                      maximum_lost_groups=1, timing_repetitions=3)
        cloud.fixed_grid(config, 20261016, False)
        for key, value in [('seeds', [20261017]), ('concat_materialized', [False]),
                           ('versions', [64]), ('maximum_lost_groups', 0),
                           ('methods', sorted(cloud.METHODS)[:-1] + ['RecoverML_exact'])]:
            changed = copy.deepcopy(config)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                cloud.fixed_grid(changed, 20261016, False)

    def fixture(self, directory):
        rows = []
        plans = []
        for method in sorted(cloud.METHODS):
            rows.append(dict(history='fixture', method=method, store_key='same',
                exact_minimum_bytes=100, retained_bytes=100, planning_median_s=2,
                fully_recoverable='True', expected_blocked=0))
            for repeat, seconds in enumerate((1, 2, 3)):
                plans.append(dict(history='fixture', method=method, repetition=repeat,
                                  retained_bytes=100, planning_s=seconds))
        with (directory / 'summary.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with gzip.open(directory / 'planner_records.json.gz', 'wt') as stream:
            json.dump(plans, stream)
        self.trace(directory, sorted(cloud.METHODS))
        return rows

    def trace(self, directory, methods):
        with gzip.open(directory / 'execution_traces.jsonl.gz', 'wt') as stream:
            stream.write(json.dumps(dict(history='fixture', store_key='same', methods=methods)) + '\n')

    def test_shared_execution_cannot_be_relabelled_or_count_method_twice(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.fixture(directory)
            cloud.plan_crosslinks(directory)
            for methods in [sorted(cloud.METHODS)[:-1], sorted(cloud.METHODS) + ['robust_local']]:
                self.trace(directory, methods)
                with self.assertRaisesRegex(ValueError, 'wrong methods'):
                    cloud.plan_crosslinks(directory)

    def test_changed_optimum_and_planner_median_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for key, value in [('exact_minimum_bytes', 99), ('planning_median_s', 0.5)]:
                rows = self.fixture(directory)
                rows[0][key] = value
                with (directory / 'summary.csv').open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    cloud.plan_crosslinks(directory)


if __name__ == '__main__':
    unittest.main()
