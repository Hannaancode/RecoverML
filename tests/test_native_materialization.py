"""Evidence transport must preserve bytes and reject corruption/traversal."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('native_transport', Path(__file__).resolve().parents[1] / 'scripts/materialize_native_baselines.py')
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)


class NativeMaterializationTests(unittest.TestCase):
    def fixture(self, root, name='evidence.txt'):
        base = root / 'results/research/native_frontier_cloud_oct16'
        base.mkdir(parents=True)
        data = b'original CRLF bytes\r\n'
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        raw = buffer.getvalue()
        part = base / 'part.bin'
        part.write_bytes(raw)
        digest = lambda value: hashlib.sha256(value).hexdigest()
        record = dict(bytes=len(raw), sha256=digest(raw), parts=[dict(path=part.relative_to(root).as_posix(),
            bytes=len(raw), sha256=digest(raw))], files={name: dict(bytes=len(data), sha256=digest(data))})
        (base / 'baseline_archives.json').write_text(json.dumps(dict(baselines={v: record for v in ('v1', 'v2', 'v3')})))
        return part, data

    def test_roundtrip_preserves_original_bytes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, data = self.fixture(root)
            output = root / 'output'
            self.assertEqual(set(transport.materialize(root, output)), {'v1', 'v2', 'v3'})
            self.assertEqual((output / 'v2/evidence.txt').read_bytes(), data)
            with self.assertRaisesRegex(ValueError, 'fresh output'):
                transport.materialize(root, output)

    def test_corrupt_part_and_unsafe_member_are_rejected(self):
        for unsafe in (False, True):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                part, _ = self.fixture(root, '../escape.txt' if unsafe else 'evidence.txt')
                if not unsafe:
                    part.write_bytes(part.read_bytes() + b'changed')
                with self.assertRaises(ValueError):
                    transport.materialize(root, root / 'output')
                self.assertFalse((root / 'escape.txt').exists())


if __name__ == '__main__':
    unittest.main()
