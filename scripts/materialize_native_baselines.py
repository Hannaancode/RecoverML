"""Restore all exact-member superseded native evidence from transport parts."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name:
        raise ValueError('Unsafe transport member path')
    return path


def materialize(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    manifest = json.loads((root / 'results/research/native_frontier_cloud_oct16/baseline_archives.json').read_bytes())
    if set(manifest['baselines']) != {'v1', 'v2', 'v3'}:
        raise ValueError('Expected all three superseded controls')
    if any((output / name).exists() for name in manifest['baselines']):
        raise ValueError('Choose a fresh output directory; never overwrite evidence')
    result = {}
    for version, record in manifest['baselines'].items():
        chunks = []
        seen = set()
        for item in record['parts']:
            relative = safe(item['path'])
            if str(relative) in seen:
                raise ValueError('Duplicate transport part')
            seen.add(str(relative))
            path = root / relative
            if not path.resolve().is_relative_to(root):
                raise ValueError('Part is outside repository')
            raw = path.read_bytes()
            if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
                raise ValueError('Transport part hash/size differs')
            chunks.append(raw)
        raw = b''.join(chunks)
        if len(raw) != record['bytes'] or sha(raw) != record['sha256']:
            raise ValueError('Assembled transport archive differs')
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            members = archive.getmembers()
            if any(not m.isfile() for m in members) or len(members) != len({m.name for m in members}):
                raise ValueError('Only distinct regular evidence files are supported')
            if {m.name for m in members} != set(record['files']):
                raise ValueError('Transport member inventory differs')
            for member in members:
                safe(member.name)
                data = archive.extractfile(member).read()
                expected = record['files'][member.name]
                if len(data) != expected['bytes'] or sha(data) != expected['sha256']:
                    raise ValueError('Transport member bytes differ')
            destination = output / version
            destination.mkdir(parents=True)
            archive.extractall(destination, filter='data')
            for name, expected in record['files'].items():
                if sha((destination / name).read_bytes()) != expected['sha256']:
                    raise ValueError('Restored evidence differs')
            result[version] = dict(files=len(members), status='PASS')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('work/native_baselines'))
    args = parser.parse_args()
    print(json.dumps(materialize(Path(__file__).resolve().parents[1], args.output), indent=2))
