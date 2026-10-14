import tempfile
import unittest
from pathlib import Path
from recoverml.core import Graph
from recoverml.published_materializers import load_source, select


class PublishedAdapterTests(unittest.TestCase):
    def test_tampered_download_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/'history_manager.py').write_text('raise RuntimeError("must not execute")\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):load_source(t)

    def test_adapter_never_awards_extra_usable_bytes(self):
        try:import networkx
        except ImportError:self.skipTest('Optional paper dependency networkx unavailable')
        g=Graph(env={});nid=g.add('test',[],{},'target',False,'target',1.,0)
        g.targets={'0':[nid]};size=g.nodes[nid].size
        class Native:
            def rank_based_materializer(self,graph,budget):
                self.budget=budget;return [g.nodes[nid].blob]
        native=Native()
        self.assertEqual(select(g,size,native),{g.nodes[nid].blob})
        self.assertEqual(native.budget,size+1)
        with self.assertRaisesRegex(RuntimeError,'exceeded'):select(g,size-1,native)
