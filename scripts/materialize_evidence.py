"""Reassemble original archived evidence from its verified Git transport parts."""
import argparse
from pathlib import Path

from verify_release import PARTS_MANIFEST, Snapshot, evidence_inventory, original_evidence_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    snapshot = Snapshot(root, args.ref)
    required = evidence_inventory(snapshot)['expected_sha256']
    for name in snapshot.json(PARTS_MANIFEST)['artifacts']:
        if name not in required:
            raise ValueError('Unrecognized historical evidence path: ' + name)
        data, _ = original_evidence_bytes(snapshot, name, required[name])
        target = root / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Existing file differs and will not be overwritten: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print('Verified original bytes: ' + name)


if __name__ == '__main__':
    main()
