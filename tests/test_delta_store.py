import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from threadpoolctl import threadpool_limits
from recoverml.core import Graph,Node,RestoreError,digest,write_store
from recoverml.encoded_store import Representation,EncodedStore
from recoverml.delta_store import DeltaRepresentation,DeltaStore,descriptor,DELTA,HEADER,open_store
from recoverml.capability_retention import restricted,contract
from recoverml.component_retention import optimize
from recoverml.scenario_retention import optimize as reference
from recoverml.witness import certificate


class DeltaStoreTests(unittest.TestCase):
    def fixture(self):
        g=Graph(env={})
        root=g.add('input',[],{},7,False,'root',0.,0,mandatory=True)
        a=np.random.default_rng(7).integers(0,256,4096,dtype=np.uint8)
        first=g.add('first',[root],{},a,True,'target',0.,0)
        b=a.copy();b[2000:2010]=0
        second=g.add('second',[first],{},b,True,'target',0.,1)
        g.targets={'0':[first],'1':[second]}
        return g,{first:'fit',second:'fit'}

    def test_exhaustive_physical_closure_and_optima_match_original_semantics(self):
        g,caps=self.fixture();rep=DeltaRepresentation(g)
        self.assertEqual(len(rep.deltas),1)
        # Add an alternate cyclic ML producer: this must not create a storage base.
        first,second=g.targets['0'][0],g.targets['1'][0]
        g.nodes['cycle']=Node('cycle','cycle',[second],{},True,'target',g.nodes[first].blob,g.nodes[first].size,0.,0)
        caps['cycle']='fit';rep=DeltaRepresentation(g)
        optional=sorted(rep.physical.keys()-rep.cost_graph.roots)
        for k in (0,1):
            faults=[[]] if k==0 else [[],['fit']];best=None
            for mask in range(1<<len(optional)):
                paid=rep.cost_graph.roots|{b for i,b in enumerate(optional) if mask>>i&1}
                stored={b for b,t in rep.full_tokens.items() if t in paid}
                while True:
                    after=stored|{b for b,t in rep.delta_tokens.items() if t in paid and rep.bases[b] in stored}
                    if after==stored:break
                    stored=after
                feasible=True
                normalized=rep.normalize(paid)
                self.assertLessEqual(sum(len(rep.physical[b][1]) for b in normalized),sum(len(rep.physical[b][1]) for b in paid))
                self.assertEqual(set(rep.files(normalized)),stored)
                for fault in faults:
                    expected=certificate(restricted(g,caps,fault),stored)
                    actual=certificate(restricted(rep.cost_graph,caps,fault),paid)
                    self.assertEqual(set(actual['available'])&g.candidates,set(expected['available']))
                    self.assertEqual(actual['complete'],expected['complete']);feasible &= actual['complete']
                    self.assertEqual(set(certificate(restricted(rep.cost_graph,caps,fault),normalized)['available'])&g.candidates,set(expected['available']))
                if feasible:
                    cost=sum(len(rep.physical[b][1]) for b in paid)
                    best=cost if best is None else min(best,cost)
            for solver in (optimize,reference):
                selected,status,diag=solver(rep.cost_graph,caps,k)
                self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
                self.assertLess(best,rep.prohibitive)
                self.assertEqual(sum(len(rep.physical[b][1]) for b in selected),best)
                rep.files(selected)

    def test_export_has_no_archive_or_ml_imports_and_counts_actual_bytes(self):
        g,caps=self.fixture();rep=DeltaRepresentation(g);selected,status,_=optimize(rep.cost_graph,caps,1)
        self.assertEqual(status,'ok');self.assertTrue(selected&set(rep.delta_tokens.values()))
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/'store';size=rep.write(selected,caps,1,store)
            expected={g.nodes[t].blob:g.archive[g.nodes[t].blob] for ts in g.targets.values() for t in ts}
            capture=Path(tmp)/'capture';write_store(g,g.candidates,capture)
            declared=Path(tmp)/'contract.json';declared.write_bytes(contract(caps,1))
            cli_store=Path(tmp)/'cli_store'
            created=subprocess.run([sys.executable,'-m','recoverml.delta_store','create','--capture',str(capture),
                '--contract',str(declared),'--output',str(cli_store)],capture_output=True,text=True)
            self.assertEqual(created.returncode,0,created.stderr);self.assertEqual(json.loads(created.stdout)['format'],'delta')
            recovered=subprocess.run([sys.executable,'-m','recoverml.delta_store','recover','--store',str(cli_store),
                '--output',str(Path(tmp)/'cli_out'),'--disable','fit'],capture_output=True,text=True)
            self.assertEqual(recovered.returncode,0,recovered.stderr)
            self.assertEqual(json.loads(recovered.stdout)['target_sha256'],{b:b for b in expected})
            g.archive.clear();rep.full.clear();rep.deltas.clear();rep.physical.clear()
            self.assertEqual(size,sum(p.stat().st_size for p in store.rglob('*') if p.is_file()))
            code='''
import importlib.abc,sys,json
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','scipy','sklearn','torch'}:raise AssertionError('ML import attempted')
sys.meta_path.insert(0,Block())
from recoverml.delta_store import open_store
print(json.dumps(open_store(sys.argv[1]).recover(sys.argv[2],disabled=['fit'])))
'''
            result=subprocess.run([sys.executable,'-c',code,str(store),str(Path(tmp)/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'PASS')
            for blob,raw in expected.items():self.assertEqual((Path(tmp)/'out'/(blob+'.pkl')).read_bytes(),raw)
            with self.assertRaises(RestoreError):EncodedStore(store)
            self.assertIsInstance(open_store(store),DeltaStore)

    def test_missing_corrupt_cyclic_oversized_nested_and_trailing_deltas_fail_closed(self):
        g,caps=self.fixture();rep=DeltaRepresentation(g);selected,_,_=optimize(rep.cost_graph,caps,1)
        blob=next(iter(rep.deltas));base=rep.bases[blob]
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/'store';rep.write(selected,caps,1,store);loaded=DeltaStore(store)
            base_path=store/'blobs'/(base+'.pkl');original_base=base_path.read_bytes()
            path=store/'blobs'/(blob+'.pkl');original=path.read_bytes()
            base_path.unlink()
            with self.assertRaises(RestoreError):loaded.load(blob)
            base_path.write_bytes(b'bad')
            with self.assertRaises(RestoreError):loaded.load(blob)
            base_path.write_bytes(original_base)
            invalid=[original[:-1],original+b'extra',original[:1]+bytes.fromhex(blob)+original[33:],
                     original[:33]+(2**63).to_bytes(8,'big')+original[41:],original[:HEADER]+bytes([DELTA])+original[HEADER+1:]]
            for data in invalid:
                path.write_bytes(data)
                with self.assertRaises(RestoreError):loaded.load(blob)
            path.write_bytes(original);self.assertEqual(loaded.load(blob),g.archive[blob])
            with self.assertRaises(ValueError):rep.files(selected|{rep.full_tokens[blob]})
            with self.assertRaises(ValueError):rep.files(selected-{rep.full_tokens[base]})
            virtual=rep.cost_graph.candidates-rep.physical.keys()
            with self.assertRaises(ValueError):rep.files(selected|{next(iter(virtual))})

    def test_all_recipe_families_replay_with_strict_environment_and_original_hashes(self):
        from recoverml.broad_workflows import capture,capabilities,execute
        with threadpool_limits(limits=1):
            for recipe in ('standard_linear','pca_neighbors','minmax_tree','robust_forest'):
                graph,_=capture('iris',recipe,4,20261027);rep=DeltaRepresentation(graph)
                for loss in ('intact','preprocessing','broad'):
                    caps,k,disabled=capabilities(graph,loss);selected,status,diag=optimize(rep.cost_graph,caps,k)
                    self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
                    with tempfile.TemporaryDirectory() as tmp:
                        store=Path(tmp)/'store';rep.write(selected,caps,k,store)
                        result=DeltaStore(store).recover(Path(tmp)/'out',disabled=disabled,replay_execute=execute)
                        self.assertEqual(result['status'],'PASS')
                        for targets in graph.targets.values():
                            for target in targets:
                                blob=graph.nodes[target].blob
                                self.assertEqual((Path(tmp)/'out'/(blob+'.pkl')).read_bytes(),graph.archive[blob])
