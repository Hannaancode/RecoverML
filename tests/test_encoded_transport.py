import hashlib
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from materialize_encoded_storage import materialize


class EncodedTransportTests(unittest.TestCase):
    def fixture(self,root):
        base=Path(__file__).resolve().parents[1]
        config=json.loads((base/'configs/encoded_storage_oct26.json').read_bytes())
        groups=json.loads((base/'configs/encoded_storage_transfer_oct26.json').read_bytes())['groups']
        manifest=dict(datasets=config['datasets'],recipes=config['recipes'],transfer_groups=groups,
            primary_source_commit='a'*40,transfer_source_commit='b'*40,artifacts=[])
        labels=[dict(kind='primary',dataset=d,recipe=r) for d,r in itertools.product(config['datasets'],config['recipes'])]
        labels.extend(dict(kind='transfer',group=g) for g in groups)
        for i,label in enumerate(labels):
            primary=label['kind']=='primary';prefix='encoded_census' if primary else 'encoded_transfer'
            name=('encoded-storage-'+label['dataset']+'-'+label['recipe'] if primary else 'encoded-transfer-'+label['group'])
            data=b'original\r\n';buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(prefix+'/data.bin',data)
            raw=buffer.getvalue();path=str(i)+'.zip';(root/path).write_bytes(raw)
            manifest['artifacts'].append(dict(label,artifact=dict(name=name,digest='sha256:'+hashlib.sha256(raw).hexdigest(),
                workflow_run=dict(head_sha=('a' if primary else 'b')*40)),
                parts=[dict(path=path,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())],
                files={prefix+'/data.bin':dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())}))
        (root/'artifact_manifest.json').write_text(json.dumps(manifest))
        return manifest

    def test_all_28_originals_preserve_exact_bytes_and_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);output=root/'out';m=materialize(root,output)
            self.assertEqual(len(m['artifacts']),28)
            self.assertEqual(len(list(output.rglob('data.bin'))),28)
            self.assertTrue(all(p.read_bytes()==b'original\r\n' for p in output.rglob('data.bin')))
            with self.assertRaises(ValueError):materialize(root,output)

    def test_missing_groups_corrupt_parts_and_traversal_are_rejected(self):
        for mode in ('missing','corrupt','traversal'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);m=self.fixture(root)
                if mode=='missing':m['artifacts'].pop()
                elif mode=='corrupt':(root/'0.zip').write_bytes(b'bad')
                else:m['artifacts'][0]['parts'][0]['path']='../outside.zip'
                (root/'artifact_manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):materialize(root,root/'out')
