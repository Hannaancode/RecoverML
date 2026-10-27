import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_encoded_transport as fixtures
from materialize_delta_storage import materialize


class DeltaTransportTests(unittest.TestCase):
    def fixture(self,root):
        old=fixtures.EncodedTransportTests().fixture(root);records=[]
        for item in old['artifacts']:
            block='primary/'+item['dataset']+'/'+item['recipe'] if item['kind']=='primary' else 'transfer/'+item['group']
            # Keep exact ZIP bytes; replace only the allowed member prefix below.
            import hashlib,io,zipfile
            data=b'original\r\n';buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('delta/data.bin',data)
            raw=buffer.getvalue();part=item['parts'][0];(root/part['path']).write_bytes(raw)
            part.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            item['artifact'].update(digest='sha256:'+part['sha256'],workflow_run={'head_sha':'a'*40})
            records.append(dict(block=block,artifact=item['artifact'],parts=item['parts'],files={'delta/data.bin':dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())}))
        m={attempt:dict(source_commit='a'*40,artifacts=copy.deepcopy(records)) for attempt in ('first','final')}
        (root/'artifact_manifest.json').write_text(json.dumps(m));return m

    def test_both_attempts_restore_exact_bytes_and_missing_duplicate_or_bad_parts_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            for attempt in ('first','final'):
                materialize(root,root/attempt,attempt)
                self.assertEqual(len(list((root/attempt).rglob('data.bin'))),28)
                self.assertTrue(all(p.read_bytes()==b'original\r\n' for p in (root/attempt).rglob('data.bin')))
                with self.assertRaises(ValueError):materialize(root,root/attempt,attempt)
        for mode in ('missing','duplicate','corrupt','traversal'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);m=self.fixture(root);records=m['final']['artifacts']
                if mode=='missing':records.pop()
                elif mode=='duplicate':records[-1]=copy.deepcopy(records[0])
                elif mode=='corrupt':(root/records[0]['parts'][0]['path']).write_bytes(b'bad')
                else:records[0]['parts'][0]['path']='../escape'
                (root/'artifact_manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):materialize(root,root/'out')
