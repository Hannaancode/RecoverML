import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from threadpoolctl import threadpool_limits
from recoverml.core import Graph,RestoreError
from recoverml.encoded_store import Representation,EncodedStore,encode,decode,variants,shuffle,unshuffle,MAGIC,MAX_METADATA
from recoverml.component_retention import optimize
from recoverml.capability_retention import restricted
from recoverml.witness import certificate


class EncodedStoreTests(unittest.TestCase):
    def fixture(self):
        graph=Graph(env={})
        root=graph.add('input',[],{},np.arange(4.),False,'source',0.,0,mandatory=True)
        features=graph.add('zero_features',[root],{},np.zeros(20000),True,'features',0.,0)
        target=graph.add('seeded_model',[features],{'seed':7},np.random.default_rng(7).normal(size=1024),True,'model',0.,0)
        graph.targets={'0':[target]}
        return graph,root,features,target,{features:'preprocessing'}

    def test_encoding_modes_roundtrip_and_corruption_size_and_trailing_are_rejected(self):
        for raw in (b'',b'a'*100000,os.urandom(4096)):
            for policy in ('identity','gzip9','adaptive'):
                with self.subTest(policy=policy,size=len(raw)):
                    data=encode(raw,policy);identity=hashlib.sha256(raw).hexdigest()
                    self.assertEqual(decode(data,len(raw),identity),raw)
                    self.assertEqual(encode(raw,policy),data)
                    for bad in (data[:-1],data+b'extra',b'\xff'+data[1:]):
                        with self.assertRaises(RestoreError):decode(bad,len(raw),identity)
                    with self.assertRaises(RestoreError):decode(data,len(raw)+1,identity)
                    with self.assertRaises(RestoreError):decode(data,len(raw),'0'*64)
        for size in range(33):
            raw=os.urandom(size)
            self.assertEqual(unshuffle(shuffle(raw)),raw)
            for data in variants(raw,'adaptive'):
                self.assertEqual(decode(data,size,hashlib.sha256(raw).hexdigest()),raw)

    def test_encoded_costs_change_optimum_without_changing_targets_and_replay_has_no_archive(self):
        graph,root,features,target,caps=self.fixture()
        raw_selected,status,_=optimize(graph,caps,1)
        self.assertEqual(status,'ok');self.assertIn(graph.nodes[target].blob,raw_selected)
        representation=Representation(graph)
        selected,status,diag=optimize(representation.cost_graph,caps,1)
        self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
        self.assertIn(graph.nodes[features].blob,selected);self.assertNotIn(graph.nodes[target].blob,selected)
        self.assertLess(representation.size(selected,caps,1),representation.size(raw_selected,caps,1))
        for disabled in ([],['preprocessing']):
            self.assertTrue(certificate(restricted(graph,caps,disabled),selected)['complete'])
        expected=graph.archive[graph.nodes[target].blob]
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/'store';output=Path(tmp)/'outputs'
            size=representation.write(selected,caps,1,store)
            self.assertEqual(size,sum(p.stat().st_size for p in store.rglob('*') if p.is_file()))
            graph.archive.clear();representation.encoded.clear()
            loaded=EncodedStore(store);self.assertEqual(loaded.graph.archive,{})
            def execute(op,values,params):
                self.assertEqual(op,'seeded_model')
                self.assertEqual(values[0].shape,(20000,))
                return np.random.default_rng(params['seed']).normal(size=1024)
            result=loaded.recover(output,disabled=['preprocessing'],replay_execute=execute,verify_environment=False)
            self.assertEqual(result['status'],'PASS')
            self.assertEqual((output/(graph.nodes[target].blob+'.pkl')).read_bytes(),expected)
            with self.assertRaises(RestoreError):loaded.recover(Path(tmp)/'strict',disabled=['preprocessing'],replay_execute=execute)

    def test_retained_export_avoids_model_imports_and_rejects_invalid_requests_and_outputs(self):
        graph,root,features,target,caps=self.fixture();blob=graph.nodes[target].blob
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/'store';output=Path(tmp)/'output'
            Representation(graph).write(graph.roots|{blob},caps,1,store)
            code='''
import importlib.abc,sys
from pathlib import Path
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','scipy','sklearn','torch'}:raise AssertionError('Model import attempted')
sys.meta_path.insert(0,Block())
from recoverml.encoded_store import EncodedStore
assert EncodedStore(sys.argv[1]).recover(sys.argv[2])['status']=='PASS'
'''
            result=subprocess.run([sys.executable,'-c',code,str(store),str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            cli=subprocess.run([sys.executable,'-m','recoverml.encoded_store','recover','--store',str(store),
                                '--output',str(Path(tmp)/'cli_output')],capture_output=True,text=True)
            self.assertEqual(cli.returncode,0,cli.stderr)
            self.assertEqual(json.loads(cli.stdout)['status'],'PASS')
            loaded=EncodedStore(store)
            for ids in ([],['unknown']):
                with self.assertRaises(ValueError):loaded.recover(output,target_ids=ids)
            with self.assertRaises(ValueError):loaded.recover(store/'outputs')
            with self.assertRaises(ValueError):loaded.recover(output,disabled=['unknown'])
            (output/(blob+'.pkl')).write_bytes(b'wrong existing result')
            with self.assertRaises(RestoreError):loaded.recover(output)
            (store/'blobs'/(blob+'.pkl')).write_bytes(b'corrupt')
            with self.assertRaises(RestoreError):loaded.load(blob)
            (store/'metadata.rml').write_bytes(MAGIC+(MAX_METADATA+1).to_bytes(8,'big')+b'0'*40)
            with self.assertRaises(RestoreError):EncodedStore(store)

    def test_all_recipe_families_preserve_strict_runtime_and_canonical_output_hashes(self):
        from recoverml.broad_workflows import capture,execute,capabilities
        with threadpool_limits(limits=1):
            for dataset in ('iris','linnerud'):
                for recipe in ('standard_linear','pca_neighbors','minmax_tree','robust_forest'):
                    graph,_=capture(dataset,recipe,1,20261026)
                    representation=Representation(graph)
                    for loss in ('intact','preprocessing','broad'):
                        caps,k,disabled=capabilities(graph,loss)
                        selected,status,_=optimize(representation.cost_graph,caps,k)
                        self.assertEqual(status,'ok')
                        with tempfile.TemporaryDirectory() as tmp:
                            store=Path(tmp)/'store';representation.write(selected,caps,k,store)
                            result=EncodedStore(store).recover(Path(tmp)/'out',disabled=disabled,replay_execute=execute)
                            self.assertEqual(result['status'],'PASS')
                            for target in graph.targets['0']:
                                blob=graph.nodes[target].blob
                                self.assertEqual((Path(tmp)/'out'/(blob+'.pkl')).read_bytes(),graph.archive[blob])
