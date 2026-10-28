import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from materialize_encoded_storage import materialize as encoded
from materialize_delta_storage import materialize as delta
from materialize_solid_storage import materialize
from audit_solid_storage import audit


class SolidAuditTests(unittest.TestCase):
    def test_originals_rebuild_and_forged_totals_sources_or_zip_fail(self):
        source=ROOT/'results/research/solid_storage_oct27'
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);old=base/'old';prior=base/'delta';current=base/'solid'
            encoded(ROOT/'results/research/encoded_storage_oct26',old)
            delta(ROOT/'results/research/delta_storage_oct27',prior)
            manifest=materialize(source,current);block=current/'primary/iris/standard_linear'
            receipt=audit(block,old,prior,manifest['source_commit'])
            self.assertEqual(receipt['status'],'PASS');self.assertEqual(receipt['conditions'],9)
            path=block/'result.json';original=path.read_bytes();record=json.loads(original)
            record['rows'][0]['production_bytes']-=1;path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,'three-candidate'):audit(block,old,prior,manifest['source_commit'])
            record=json.loads(original);record['source_sha256']['src/recoverml/solid_store.py']='0'*64;path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,'source inventory'):audit(block,old,prior,manifest['source_commit'])
            damaged=base/'damaged';shutil.copytree(source,damaged)
            zip_path=damaged/manifest['artifacts'][0]['path'];data=bytearray(zip_path.read_bytes());data[-1]^=1;zip_path.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'ZIP differs'):materialize(damaged,base/'bad')
            with self.assertRaisesRegex(ValueError,'fresh'):materialize(source,current)
