"""Export fully retained target FILES using hashes, without loading model objects.

Exact file export does not deserialize values or promise model compatibility.
Missing targets return None so callers can choose the normal replay path.
Corrupt retained targets fail closed. This module uses the standard library.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

from .core import RestoreError


def fingerprint(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def export_retained_targets(store, output):
    store, output = Path(store), Path(output)
    started = time.perf_counter()
    manifest = json.loads((store / 'manifest.json').read_bytes())
    if manifest['schema'] != 1:
        raise ValueError('Unsupported manifest schema')
    nodes = {n['id']: n for n in manifest['nodes']}
    if len(nodes) != len(manifest['nodes']):
        raise ValueError('Duplicate manifest node')
    targets = {}
    for requested in manifest['targets'].values():
        for node_id in requested:
            node = nodes[node_id]
            blob, size = node['blob'], node['size']
            if re.fullmatch(r'[0-9a-f]{64}', blob) is None or type(size) is not int or size < 0:
                raise ValueError('Invalid target content identity')
            if blob in targets and targets[blob] != size:
                raise ValueError('Conflicting physical target sizes')
            targets[blob] = size
    if not targets or not all((store / 'blobs' / (blob + '.pkl')).is_file() for blob in targets):
        return None
    # Verify all sources before materializing output. No pickle is interpreted.
    for blob, size in targets.items():
        source = store / 'blobs' / (blob + '.pkl')
        if source.stat().st_size != size or fingerprint(source) != blob:
            raise RestoreError('Corrupt retained target file: ' + blob)
    output.mkdir(parents=True, exist_ok=True)
    for blob, size in targets.items():
        source, destination = store / 'blobs' / (blob + '.pkl'), output / (blob + '.pkl')
        if destination.exists():
            if not source.samefile(destination) and (destination.stat().st_size != size or fingerprint(destination) != blob):
                raise RestoreError('Existing export file differs: ' + blob)
        else:
            shutil.copyfile(source, destination)
            if destination.stat().st_size != size or fingerprint(destination) != blob:
                raise RestoreError('Exported target file differs: ' + blob)
    return dict(status='PASS', mode='retained_file_export', core_elapsed_s=time.perf_counter()-started,
                target_sha256={blob: blob for blob in targets}, operations=[],
                qualification='Exact retained file bytes only. No model is deserialized and no value-level runtime compatibility is asserted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = export_retained_targets(args.store, args.output)
    if result is None:
        raise SystemExit('Some target files are not retained; use the normal replay path')
    print(json.dumps(result, indent=2))
