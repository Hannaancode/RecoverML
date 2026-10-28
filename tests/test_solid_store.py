import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from threadpoolctl import threadpool_limits
from recoverml.core import Graph,RestoreError,canonical,digest,write_store
from recoverml.encoded_store import Representation,encode,metadata
from recoverml.solid_store import SolidRepresentation,SolidStore,container,unpack,MAGIC,MAX_SOLID_BYTES
from recoverml.delta_store import open_store
from recoverml.capability_retention import contract
from recoverml.component_retention import optimize


class SolidStoreTests(unittest.TestCase):
    def fixture(self):
        graph=Graph(env={});root=graph.add('input',[],{},7,False,'root',0.,0,mandatory=True)
        values=np.random.default_rng(9).integers(0,256,12000,dtype=np.uint8);caps={}
        for version in range(4):
            changed=values.copy();changed[3000+version]=version
            target=graph.add('fit',[root],{},changed,True,'target',0.,version)
            graph.targets[str(version)]=[target];caps[target]='fit'
        return graph,caps

    def test_matches_published_control_bytes_and_cli_selects_smallest_store(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from benchmark_delta_storage import solid_control
        graph,caps=self.fixture();selected=graph.candidates;rep=SolidRepresentation(graph)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);store=base/'store';size=rep.write(iter(selected),caps,1,store)
            control=solid_control(selected,graph.archive,metadata(graph,caps,1,'adaptive'),{})
            self.assertEqual(size,control['bytes'])
            self.assertEqual({p.name:dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in store.iterdir()},control['inventory'])
            self.assertLess(size,Representation(graph).size(selected,caps,1))
            self.assertIsInstance(open_store(store),SolidStore)
            capture=base/'capture';write_store(graph,graph.candidates,capture)
            declared=base/'contract.json';declared.write_bytes(contract(caps,1))
            created=subprocess.run([sys.executable,'-m','recoverml.solid_store','create','--capture',str(capture),
                '--contract',str(declared),'--output',str(base/'auto')],capture_output=True,text=True)
            self.assertEqual(created.returncode,0,created.stderr);receipt=json.loads(created.stdout)
            self.assertEqual(receipt['store_bytes'],min(receipt['candidate_bytes'].values()))
            self.assertEqual(set(receipt['candidate_bytes']),{'flat','delta','solid-flat','solid-flat-local','solid-delta-local'})
            recovered=subprocess.run([sys.executable,'-m','recoverml.solid_store','recover','--store',str(base/'auto'),
                '--output',str(base/'out'),'--disable','fit'],capture_output=True,text=True)
            self.assertEqual(recovered.returncode,0,recovered.stderr)
            for target in graph.targets.values():
                blob=graph.nodes[target[0]].blob;self.assertEqual((base/'out'/(blob+'.pkl')).read_bytes(),graph.archive[blob])

    def test_export_without_capture_or_ml_imports_and_request_validation(self):
        graph,caps=self.fixture();expected=dict(graph.archive)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);store=base/'store';SolidRepresentation(graph).write(graph.candidates,caps,1,store)
            graph.archive.clear()
            code='''
import importlib.abc,sys,json
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','scipy','sklearn','torch'}:raise AssertionError('ML import attempted')
sys.meta_path.insert(0,Block())
from recoverml.solid_store import SolidStore
print(json.dumps(SolidStore(sys.argv[1]).recover(sys.argv[2],disabled=['fit'])))
'''
            result=subprocess.run([sys.executable,'-c',code,str(store),str(base/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);receipt=json.loads(result.stdout)
            self.assertEqual(receipt['mode'],'solid_export');self.assertEqual(receipt['temporary_store_bytes'],0)
            for blob in receipt['target_sha256']:self.assertEqual((base/'out'/(blob+'.pkl')).read_bytes(),expected[blob])
            loaded=SolidStore(store)
            for ids in ([],['unknown']):
                with self.assertRaises(ValueError):loaded.recover(base/'out',target_ids=ids)
            with self.assertRaises(ValueError):loaded.recover(store/'out')
            with self.assertRaises(ValueError):loaded.recover(base/'out',disabled=['unknown'])
            blob=next(iter(receipt['target_sha256']));(base/'out'/(blob+'.pkl')).write_bytes(b'wrong')
            with self.assertRaises(RestoreError):loaded.recover(base/'out')

    def test_malformed_corrupt_trailing_duplicate_and_missing_members_fail_closed(self):
        graph,caps=self.fixture();header=metadata(graph,caps,1,'adaptive')
        entries=[('metadata.rml',header)]+[(b+'.pkl',graph.archive[b]) for b in sorted(graph.candidates)]
        valid=container(entries)
        def forged(index,body):
            index=canonical(index);payload=len(index).to_bytes(8,'big')+index+body
            return MAGIC+len(payload).to_bytes(8,'big')+bytes.fromhex(digest(payload))+encode(payload,'identity')
        invalid=[valid[:-1],valid+b'trailing',valid[:len(MAGIC)]+(MAX_SOLID_BYTES+1).to_bytes(8,'big')+valid[len(MAGIC)+8:],
                 container(entries+[entries[1]]),container([('../outside',b'x')]),
                 forged([['0'*64+'.pkl',2,digest(b'x')]],b'x'),forged([],b'x'),
                 forged([['0'*64+'.pkl',1,'0'*64]],b'x')]
        for bad in invalid:
            with self.subTest(bytes=len(bad)),self.assertRaises(RestoreError):unpack(bad)
        with tempfile.TemporaryDirectory() as temporary:
            store=Path(temporary);archive=store/'archive.rml'
            archive.write_bytes(container(entries));self.assertEqual(SolidStore(store).retained,graph.candidates)
            (store/'metadata.rml').write_bytes(header)
            with self.assertRaises(RestoreError):SolidStore(store)
            archive.write_bytes(container(entries[1:]));self.assertEqual(SolidStore(store).retained,graph.candidates)
            (store/'metadata.rml').unlink()
            with self.assertRaises(RestoreError):SolidStore(store)
            root=next(iter(graph.roots));archive.write_bytes(container([e for e in entries if e[0]!=root+'.pkl']))
            with self.assertRaises(RestoreError):SolidStore(store)
            archive.write_bytes(container(entries+[('0'*64+'.pkl',b'unknown')]))
            with self.assertRaises(RestoreError):SolidStore(store)

    def test_strict_replay_all_recipe_families_and_loss_contracts(self):
        from recoverml.broad_workflows import capture,capabilities,execute
        with threadpool_limits(limits=1):
            for recipe in ('standard_linear','pca_neighbors','minmax_tree','robust_forest'):
                graph,_=capture('iris',recipe,4,20261027);flat=Representation(graph)
                for loss in ('intact','preprocessing','broad'):
                    caps,k,disabled=capabilities(graph,loss);selected,status,_=optimize(flat.cost_graph,caps,k)
                    self.assertEqual(status,'ok')
                    with tempfile.TemporaryDirectory() as temporary:
                        base=Path(temporary);SolidRepresentation(graph).write(selected,caps,k,base/'store')
                        loaded=SolidStore(base/'store');self.assertFalse(loaded.graph.archive)
                        result=loaded.recover(base/'out',disabled=disabled,replay_execute=execute)
                        self.assertEqual(result['status'],'PASS')
                        for targets in graph.targets.values():
                            for target in targets:
                                blob=graph.nodes[target].blob;self.assertEqual((base/'out'/(blob+'.pkl')).read_bytes(),graph.archive[blob])
                        if result['mode']=='solid_replay':self.assertGreater(result['temporary_store_bytes'],0)
                        loaded.graph.env={}
                        if any(graph.nodes[t].blob not in selected for ts in graph.targets.values() for t in ts):
                            # Tamper the saved environment, not only the in-memory graph.
                            from recoverml.encoded_store import parse_metadata,MAGIC as METADATA_MAGIC
                            import zlib
                            record=parse_metadata(loaded.header);record['graph']['environment']={};raw=canonical(record)
                            loaded.header=METADATA_MAGIC+len(raw).to_bytes(8,'big')+bytes.fromhex(digest(raw))+zlib.compress(raw,9)
                            with self.assertRaises(RestoreError):loaded.recover(base/'strict',disabled=disabled,replay_execute=execute)
