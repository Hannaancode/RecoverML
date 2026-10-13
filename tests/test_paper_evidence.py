import unittest
from recoverml.paper_evidence import cluster_interval


class PaperEvidenceTests(unittest.TestCase):
    def test_repeated_widths_do_not_create_independent_seed_subjects(self):
        base=[dict(repeat=str(i),speedup_v2_v4=str(x))
              for i,x in enumerate((.8,1.,1.2,1.6,2.))]
        repeated=[dict(r,width=str(w)) for r in base for w in (4,16,32)]
        self.assertEqual(cluster_interval(base),cluster_interval(repeated))
