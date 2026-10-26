import io
import sys
import tarfile
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_encoded_storage import check_grid,files


class EncodedAuditTests(unittest.TestCase):
    def test_request_denominators_reject_missing_duplicate_and_relabelled_scenarios(self):
        rows=[dict(case='fixed',method=m,disabled=list(f)) for m in ('ours','control') for f in ((),('lost',))]
        check_grid(rows,['fixed'],['ours','control'],{'fixed':[(),('lost',)]})
        for bad in (rows[:-1],rows+[rows[0]],[dict(r,disabled=['different']) for r in rows]):
            with self.assertRaises(ValueError):check_grid(bad,['fixed'],['ours','control'],{'fixed':[(),('lost',)]})

    def test_unsafe_or_duplicate_archive_members_cannot_enter_an_audit(self):
        for names in (['../escape'],['same','same'],['C:/escape'],['directory\\escape']):
            with self.subTest(names=names),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'input.tar.gz'
                with tarfile.open(path,'w:gz') as archive:
                    for name in names:
                        member=tarfile.TarInfo(name);member.size=1;archive.addfile(member,io.BytesIO(b'x'))
                with self.assertRaises(ValueError):files(path)
