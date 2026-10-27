import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_delta_storage import audit
from benchmark_delta_storage import run,dump,ROOT
from materialize_encoded_storage import materialize
from recoverml.core import digest


class DeltaAuditTests(unittest.TestCase):
    def test_complete_roundtrip_audit_rejects_missing_rows_and_forged_byte_counts(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);originals=root/'originals';output=root/'run'
            materialize(ROOT/'results/research/encoded_storage_oct26',originals)
            run(originals,'primary/iris/standard_linear',output)
            result=audit(originals,output,preflight=True)
            self.assertEqual(result['conditions'],9);self.assertEqual(result['complete'],9)
            conditions=json.loads((output/'conditions.json').read_bytes());report=json.loads((output/'report.json').read_bytes())
            missing=conditions[:-1];forged=copy.deepcopy(conditions)
            forged[0]['methods']['delta_exact']['bytes']-=1
            for bad in (missing,forged):
                dump(output/'conditions.json',bad)
                altered=copy.deepcopy(report);altered['closed_sha256']['conditions.json']=digest((output/'conditions.json').read_bytes())
                dump(output/'report.json',altered)
                with self.assertRaises(ValueError):audit(originals,output,preflight=True)
