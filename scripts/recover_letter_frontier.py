"""Recover recorded frontier payloads without inventing the lost archive bytes.

The shared preprocessing inputs also exist in a preserved preflight archive.
Their full-study hashes and sizes must all match before producing a separately
named, deterministic replacement container. No model is trained or unpickled.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def recover(root, preflight, output, receipt):
    study = root / 'results/research/gigabyte_letter_oct16'
    membership = json.loads((study / 'store_membership.json').read_bytes())
    inventory = json.loads((study / 'blob_inventory.json').read_bytes())
    wanted = set(membership['frontier_selected'])
    contents = {}
    with tarfile.open(preflight, 'r:gz') as archive:
        for blob in sorted(wanted):
            name = 'blobs/' + blob + '.pkl'
            data = archive.extractfile(name).read()
            if sha(data) != blob or len(data) != inventory[blob]['bytes']:
                raise ValueError('Recorded full-study payload differs: ' + blob)
            contents[name] = data
    if sum(map(len, contents.values())) != membership['frontier_payload_bytes']:
        raise ValueError('Full-study retained payload byte total differs')
    contents['manifest.json'] = (study / 'manifest.json').read_bytes()
    contents['capability_contract.json'] = (study / 'preprocessing_capability_contract.json').read_bytes()
    if output.name == 'selected_frontier.tar.gz' or output.exists() or receipt.exists():
        raise ValueError('Use a new replacement name and preserve the missing original identity')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                for name, data in sorted(contents.items()):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    member.mode = 0o644
                    archive.addfile(member, io.BytesIO(data))
    with tarfile.open(output, 'r:gz') as archive:
        restored = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    if restored != contents:
        raise ValueError('Replacement archive roundtrip differs')
    result = dict(status='PASS', kind='PAYLOAD_EQUIVALENT_RECONSTRUCTION_NOT_ORIGINAL_ARCHIVE',
        original_archive_sha256=membership['frontier_archive_sha256'], original_archive_bytes_recovered=False,
        source_preflight=str(preflight.relative_to(root)), source_preflight_sha256=sha(preflight.read_bytes()),
        replacement=str(output.relative_to(root)), replacement_sha256=sha(output.read_bytes()),
        replacement_bytes=output.stat().st_size, payload_files=len(wanted),
        payload_bytes=membership['frontier_payload_bytes'],
        members=[dict(path=name, bytes=len(data), sha256=sha(data)) for name, data in sorted(contents.items())],
        measurements_changed=False, models_retrained=False,
        qualification='All four payloads match the existing full-study hashes and sizes. Manifest and contract bytes are copied unchanged. The missing original archive hash remains an unresolved provenance record and is not replaced by the new container hash.')
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = recover(Path(__file__).resolve().parents[1], args.preflight.resolve(), args.output.resolve(), args.receipt.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != 'members'}, indent=2))
