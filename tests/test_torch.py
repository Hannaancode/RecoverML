import importlib.util
import tempfile
import unittest
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from recoverml.core import Graph,DiskRestorer,RestoreError,pack,write_store
from recoverml.operators import execute


@unittest.skipUnless(importlib.util.find_spec('torch'),'optional PyTorch dependency')
class TorchTests(unittest.TestCase):
    def setUp(self):
        import torch
        torch.set_num_threads(1)
        self.limits=threadpool_limits(limits=1);self.limits.__enter__()
    def tearDown(self):
        self.limits.__exit__(None,None,None)

    def fixture(self,architecture):
        rng=np.random.default_rng(10);g=Graph()
        x=(rng.normal(size=(32,1,8,8)).astype('float32') if architecture=='cnn'
           else rng.integers(1,30,size=(32,8),dtype=np.int64))
        y=np.arange(32)%2;split=(np.arange(24),np.arange(24,32))
        nodes=[g.add('input',[],{'kind':kind},val,False,'torch',0.,0,True)
               for kind,val in zip(('x','y','split'),(x,y,split))]
        params=dict(architecture=architecture,classes=2,seed=10,epochs=1,
            learning_rate=.003,batch_size=8,vocabulary_size=32,sequence_length=8)
        state=execute('torch_train',[x,y,split],params)
        nid=g.add('torch_train',nodes,params,state,True,'torch',.001,0)
        pred=execute('torch_predict',[state,x,split],{})
        pid=g.add('torch_predict',[nid,nodes[0],nodes[2]],{},pred,True,'torch',.001,0)
        g.targets={'0':[nid,pid]}
        return g

    def test_cnn_weight_and_prediction_exact_replay(self):
        self.check('cnn')

    def test_transformer_weight_and_prediction_exact_replay(self):
        self.check('text_transformer')

    def check(self,architecture):
        g=self.fixture(architecture)
        with tempfile.TemporaryDirectory() as folder:
            store=Path(folder)/'store';write_store(g,g.roots,store)
            rg=Graph.read(store/'manifest.json')
            values=DiskRestorer(rg,store).version('0')
            for nid,val in zip(g.targets['0'],values):
                self.assertEqual(pack(val),g.archive[g.nodes[nid].blob])
            self.assertEqual(rg.archive,{})

    def test_loaded_weights_produce_exact_predictions(self):
        g=self.fixture('cnn');mid=g.targets['0'][0]
        with tempfile.TemporaryDirectory() as folder:
            store=Path(folder)/'store';write_store(g,g.roots|{g.nodes[mid].blob},store)
            restorer=DiskRestorer(Graph.read(store/'manifest.json'),store)
            restorer.version('0')
            self.assertTrue(any(t['action']=='replay' and t['node']==g.targets['0'][1]
                                for t in restorer.trace))

    def test_torch_operator_environment_change_is_rejected(self):
        g=self.fixture('cnn');g.env['torch_operator_sha256']='tampered'
        with tempfile.TemporaryDirectory() as folder:
            store=Path(folder)/'store';write_store(g,g.roots,store)
            with self.assertRaisesRegex(RestoreError,'environment'):
                DiskRestorer(Graph.read(store/'manifest.json'),store)

    def test_empty_text_sequences_have_finite_probabilities(self):
        from recoverml.torch_ops import predict,train
        x=np.zeros((32,8),dtype=np.int64);y=np.arange(32)%2
        split=(np.arange(24),np.arange(24,32))
        params=dict(architecture='text_transformer',classes=2,seed=10,epochs=1,
            learning_rate=.003,batch_size=8,vocabulary_size=32,sequence_length=8)
        checkpoint=train([x,y,split],params)
        probabilities=predict([checkpoint,x,split])
        self.assertTrue(np.isfinite(probabilities).all())
        np.testing.assert_allclose(probabilities.sum(1),1.,atol=1e-6)
