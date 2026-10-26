"""Exact file export must stay safe, lightweight and distinct from model loading."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from recoverml.core import RestoreError
from recoverml.file_export import export_retained_targets


class FileExportTests(unittest.TestCase):
    def fixture(self, temporary):
        store = Path(temporary) / 'store'
        (store / 'blobs').mkdir(parents=True)
        raw = b'these exact retained bytes are not a pickle'
        blob = hashlib.sha256(raw).hexdigest()
        (store / 'blobs' / (blob + '.pkl')).write_bytes(raw)
        manifest = dict(schema=1, environment={'model_loading': 'unsupported'},
            nodes=[dict(id='target', blob=blob, size=len(raw))], targets={'0': ['target']})
        (store / 'manifest.json').write_text(json.dumps(manifest))
        return store, Path(temporary) / 'output', blob, raw

    def test_export_is_exact_without_deserializing_values_or_asserting_runtime_compatibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            store, output, blob, raw = self.fixture(temporary)
            receipt = export_retained_targets(store, output)
            self.assertEqual((output / (blob + '.pkl')).read_bytes(), raw)
            self.assertEqual(receipt['target_sha256'], {blob: blob})
            self.assertIn('No model is deserialized', receipt['qualification'])

    def test_missing_target_returns_fallback_without_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            store, output, blob, _ = self.fixture(temporary)
            (store / 'blobs' / (blob + '.pkl')).unlink()
            self.assertIsNone(export_retained_targets(store, output))
            self.assertFalse(output.exists())

    def test_requested_retained_subset_does_not_need_or_export_other_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            store,output,blob,raw=self.fixture(temporary)
            manifest=json.loads((store/'manifest.json').read_bytes())
            manifest['nodes'].append(dict(id='missing',blob='a'*64,size=12))
            manifest['targets']['1']=['missing']
            (store/'manifest.json').write_text(json.dumps(manifest))
            self.assertIsNone(export_retained_targets(store,output))
            receipt=export_retained_targets(store,output,target_ids=['target'])
            self.assertEqual(receipt['target_sha256'],{blob:blob})
            self.assertEqual(list(output.iterdir()),[output/(blob+'.pkl')])
            for invalid in ([],['unknown']):
                with self.assertRaises(ValueError):export_retained_targets(store,output,target_ids=invalid)

    def test_corrupt_retention_or_existing_output_fails_closed(self):
        for corrupt_source in (True, False):
            with self.subTest(source=corrupt_source), tempfile.TemporaryDirectory() as temporary:
                store, output, blob, _ = self.fixture(temporary)
                if corrupt_source:
                    (store / 'blobs' / (blob + '.pkl')).write_bytes(b'changed')
                else:
                    output.mkdir()
                    (output / (blob + '.pkl')).write_bytes(b'changed')
                with self.assertRaises(RestoreError):
                    export_retained_targets(store, output)

    def test_import_does_not_load_numerical_or_model_libraries(self):
        result = subprocess.run([sys.executable, '-c',
            "import sys; import recoverml.file_export, recoverml.file_recovery; assert not ({'numpy','scipy','sklearn','torch'} & set(sys.modules))"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
