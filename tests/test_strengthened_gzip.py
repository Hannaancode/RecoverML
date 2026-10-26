import hashlib
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from strengthen_encoded_gzip import stronger
from recoverml.core import Graph,digest
from recoverml.encoded_store import Representation,metadata


class StrengthenedGzipTests(unittest.TestCase):
    def test_raw_fallback_removes_compression_overhead_and_saved_proof_cannot_be_forged(self):
        graph=Graph(env={})
        graph.add('input',[],{},bytes(range(32)),False,'source',0.,0,mandatory=True)
        target=graph.add('external',[],{},bytes(range(64,80)),False,'target',0.,0)
        graph.targets={'0':[target]}
        adaptive=Representation(graph);gz=Representation(graph,policy='gzip9');objects={};payloads={}
        for blob in graph.candidates:
            item=dict(raw_bytes=graph.sizes()[blob])
            for policy,representation in [('adaptive',adaptive),('gzip9',gz)]:
                raw=representation.encoded[blob];identity=digest(raw);objects[identity+'.bin']=raw;item[policy]=identity
            payloads[blob]=item
        header=metadata(graph,{},0,'adaptive')
        result=stronger('fixture',graph,{},0,payloads,objects,header,adaptive.size(graph.candidates,{},0))
        self.assertEqual(result['raw_fallback_selected'],2)
        self.assertEqual(result['strong_gzip_bytes'],result['adaptive_bytes'])
        self.assertEqual(stronger('fixture',graph,{},0,payloads,objects,header,result['adaptive_bytes'],result),result)
        with self.assertRaises(ValueError):
            stronger('fixture',graph,{},0,payloads,objects,header,result['adaptive_bytes'],dict(result,strong_gzip_bytes=result['strong_gzip_bytes']+1))
