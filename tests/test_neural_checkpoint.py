import tempfile
import unittest
from pathlib import Path
from threadpoolctl import threadpool_limits
from recoverml.core import pack,unpack,Graph,write_store
from recoverml.witness_pipeline import capture
from recoverml.capability_ops import restore_mlp
from recoverml.capability_retention import CapabilityRestorer


class NeuralCheckpointTests(unittest.TestCase):
    def test_canonical_roundtrip_and_exact_predictions(self):
        import numpy as np
        with threadpool_limits(limits=1):
            graph,_=capture('iris',3,'npy',1,dual_scalers=True,estimator='mlp')
            node=next(n for n in graph.nodes.values() if n.op=='train_mlp')
            raw=graph.archive[node.blob];checkpoint=unpack(raw)
            self.assertEqual(pack(unpack(pack(checkpoint))),raw)
            features=next(n for n in graph.nodes.values() if n.op=='external_features')
            x=unpack(graph.archive[features.blob])
            self.assertTrue(np.array_equal(restore_mlp(checkpoint).predict_proba(x),
                restore_mlp(unpack(pack(checkpoint))).predict_proba(x)))

    def test_loaded_checkpoint_and_prediction_bytes_match_capture(self):
        with threadpool_limits(limits=1):
            graph,_=capture('iris',4,'npy',1,dual_scalers=True,estimator='mlp')
            targets=graph.targets['0'];retained=graph.roots|{graph.nodes[t].blob for t in targets}
            with tempfile.TemporaryDirectory() as t:
                store=Path(t)/'store';write_store(graph,retained,store)
                values=CapabilityRestorer(Graph.read(store/'manifest.json'),store,{},[]).version('0')
                self.assertTrue(all(pack(v)==graph.archive[graph.nodes[n].blob] for n,v in zip(targets,values)))
