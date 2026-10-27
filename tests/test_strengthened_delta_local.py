import copy
import io
import json
from pathlib import Path
import random
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from strengthen_delta_local import block
from recoverml.core import Graph,Node,canonical,digest
from recoverml.encoded_store import Representation,metadata
from recoverml.delta_store import DeltaRepresentation


class StrongDeltaLocalTests(unittest.TestCase):
    def test_prior_choices_are_kept_and_forged_converted_receipts_are_rejected(self):
        a=random.Random(7).randbytes(2048);b=a[:1024]+b'changedxyz'+a[1034:]
        raw={digest(x):x for x in (b'root',a,b)};graph=Graph(env={});ids=['root','first','second']
        for nid,data in zip(ids,(b'root',a,b)):
            graph.nodes[nid]=Node(nid,'input' if nid=='root' else 'fit',[] if nid=='root' else ['root'],{},nid!='root','test',digest(data),len(data),0.,0)
        graph.roots={digest(b'root')};graph.targets={'0':['first','second']};caps={'first':'fit','second':'fit'}
        flat=Representation(graph,raw);rep=DeltaRepresentation(graph,raw,flat.encoded);tokens=rep.choices(graph.candidates)
        old_bytes=len(metadata(graph,caps,1,'adaptive'))+sum(map(len,flat.encoded.values()))
        new_bytes=rep.size(tokens,caps,1);case='test';key='primary/iris/standard_linear'
        cases=[dict(case=case,graph=graph,caps=caps,k=1)]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prior=root/'prior'/key;final=root/'final'/key;prior.mkdir(parents=True);final.mkdir(parents=True)
            (prior/'plans.json').write_text(json.dumps([dict(case=case,method='adaptive_local',actual_bytes=old_bytes,selected=sorted(graph.candidates))]))
            (final/'conditions.json').write_text(json.dumps([dict(case=case,status='COMPLETE',production_bytes=new_bytes,
                methods={'delta_local':dict(bytes=new_bytes)})]))
            (final/'encoding_inventory.json').write_text(json.dumps({digest(canonical(graph.manifest())):dict(deltas={b:digest(v) for b,v in rep.deltas.items()},bases=rep.bases)}))
            with tarfile.open(final/'objects.tar.gz','w:gz') as archive:
                for data in rep.deltas.values():
                    info=tarfile.TarInfo(digest(data)+'.bin');info.size=len(data);archive.addfile(info,io.BytesIO(data))
            with patch('strengthen_delta_local.inputs',return_value=(cases,raw,flat.encoded,{})):
                result=block(root/'prior',root/'final',key)
                self.assertLessEqual(result['rows'][0]['strong_local_bytes'],old_bytes)
                self.assertEqual(result['rows'][0]['decoded_sha256'],{b:b for b in graph.candidates})
                block(root/'prior',root/'final',key,result)
                forged=copy.deepcopy(result);forged['rows'][0]['strong_local_bytes']-=1
                with self.assertRaises(ValueError):block(root/'prior',root/'final',key,forged)
