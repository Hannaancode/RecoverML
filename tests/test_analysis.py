import csv
import json
import tempfile
import unittest
from pathlib import Path
from recoverml.analysis import analyze


class AnalysisTests(unittest.TestCase):
    def test_v4_is_plotted_and_nondeterministic_panel_is_not_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            rows=[]
            for policy in ('recoverability_v3','recoverability_v4','full_snapshot'):
                for fraction in (.5,1.):
                    rows.append(dict(policy=policy,budget_fraction=fraction,
                        exact=True,within_budget=True,protect_intermediate=False,
                        retained_bytes=500,full_bytes=1000,planning_s=.001,
                        restore_s=.002,dataset='digits',rows=1797,
                        boundary='nondeterministic',change='parameters',branches=1,
                        case_id='case00-rep0',status='exact',error=''))
            with (path/'raw_requests.csv').open('w',newline='') as h:
                writer=csv.DictWriter(h,fieldnames=list(rows[0]))
                writer.writeheader();writer.writerows(rows)
            result=analyze(path)
            self.assertEqual(result['proposed_policy'],'recoverability_v4')
            self.assertIn('recoverability_v4',result['plotted_policies'])
            self.assertEqual(result['proposed_exact'],2)
            self.assertTrue((path/'success_by_budget.png').is_file())
