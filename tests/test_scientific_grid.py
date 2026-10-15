import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('audit_analysis',Path(__file__).parents[1]/'scripts/analyze_scientific_audit.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ScientificGridTests(unittest.TestCase):
    def setUp(self):
        self.protocol=dict(workflows=['a','b'],seeds=[1],capability_scopes=['broad'],loss_bounds=[1],
            optional_snapshot_budget_fractions=[.5],methods=['exact'])
        self.rows=[dict(history=h,scope='broad',k=1,budget_fraction=.5,policy='exact') for h in ('a-1','b-1')]

    def test_capture_failure_cannot_shrink_the_declared_denominator(self):
        errors=module.grid_errors(self.protocol,[dict(history='a-1')],self.rows[:1])
        self.assertIn('Missing or unexpected declared capture history',errors)
        self.assertIn('Incomplete declared grid',errors)

    def test_repeated_success_cannot_replace_an_omitted_condition(self):
        errors=module.grid_errors(self.protocol,[dict(history='a-1'),dict(history='b-1')],[self.rows[0]]*2)
        self.assertIn('Duplicate summary condition',errors)
        self.assertIn('Incomplete declared grid',errors)

    def test_equal_counts_cannot_hide_wrong_raw_version_identity(self):
        expected={('a-k1','exact',.5,'0',()),('a-k1','exact',.5,'1',())}
        actual=[('a-k1','exact',.5,'0',()),('a-k1','exact',.5,'2',())]
        self.assertIn('Incomplete manifest-derived raw request grid',module.request_grid_errors(expected,actual))

    def test_repeated_raw_request_does_not_fill_the_declared_grid(self):
        request=('a-k1','exact',.5,'0',())
        self.assertIn('Duplicate declared raw request',module.request_grid_errors({request},[request,request]))


if __name__=='__main__':unittest.main()
