import hashlib,io,itertools,json,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from materialize_recovery_census import materialize


class CensusTransportTests(unittest.TestCase):
    def fixture(self,root,unsafe=False):
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/recovery_census_oct26.json').read_bytes())
        manifest=dict(source_commit='0'*40,datasets=config['datasets'],recipes=config['recipes'],artifacts=[])
        for i,(dataset,recipe) in enumerate(itertools.product(config['datasets'],config['recipes'])):
            name='../outside.bin' if unsafe and i==0 else 'census/data.bin'
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(name,b'exact original bytes\r\n')
            raw=buffer.getvalue();part=str(i)+'.zip';(root/part).write_bytes(raw)
            manifest['artifacts'].append(dict(dataset=dataset,recipe=recipe,
                artifact=dict(name='recovery-census-'+dataset+'-'+recipe,
                    workflow_run=dict(head_sha='0'*40),digest='sha256:'+hashlib.sha256(raw).hexdigest()),
                parts=[dict(path=part,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())],
                files={name:dict(bytes=22,sha256=hashlib.sha256(b'exact original bytes\r\n').hexdigest())}))
        (root/'artifact_manifest.json').write_text(json.dumps(manifest))
        return manifest

    def test_all_catalogue_members_preserve_bytes_and_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root);output=root/'restored'
            result=materialize(root,output)
            self.assertEqual(len(result['artifacts']),24)
            for record in result['artifacts']:
                self.assertEqual((output/record['dataset']/record['recipe']/'data.bin').read_bytes(),b'exact original bytes\r\n')
            with self.assertRaises(ValueError):materialize(root,output)

    def test_missing_groups_corrupt_parts_and_traversal_are_rejected(self):
        for mode in ('missing','corrupt','traversal'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);m=self.fixture(root,unsafe=mode=='traversal')
                if mode=='missing':
                    m['artifacts'].pop();(root/'artifact_manifest.json').write_text(json.dumps(m))
                elif mode=='corrupt':(root/'0.zip').write_bytes(b'corrupt')
                with self.assertRaises(ValueError):materialize(root,root/'restored')
