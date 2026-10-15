#!/usr/bin/env python3
"""Extract one exact retained store from the lossless deduplicated archive."""
import argparse
import json
from pathlib import Path
import tarfile

from recoverml.core import canonical, digest
from recoverml.capability_retention import contract


def restore(archive, condition, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'blobs').mkdir()
    with tarfile.open(archive, 'r:gz') as tar:
        records = json.load(tar.extractfile('store_index.json'))
        matches = [record for record in records if record['condition_id'] == condition]
        if len(matches) != 1:
            raise ValueError('Exactly one known condition ID required')
        record = matches[0]
        (destination / 'manifest.json').write_bytes(canonical(record['manifest']))
        (destination / 'capability_contract.json').write_bytes(contract(record['capabilities'], record['k']))
        for blob in record['selected']:
            raw = tar.extractfile('payload_blobs/' + blob + '.pkl').read()
            if digest(raw) != blob:
                raise ValueError('Archive payload SHA-256 mismatch')
            (destination / 'blobs' / (blob + '.pkl')).write_bytes(raw)
    print(json.dumps(dict(condition_id=condition, selected_blobs=len(record['selected']),
                         destination=str(destination), sha256_verified=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('condition')
    parser.add_argument('destination')
    args = parser.parse_args()
    restore(args.archive, args.condition, args.destination)
