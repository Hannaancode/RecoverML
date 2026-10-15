#!/usr/bin/env python3
"""Acquire all STARE images and Adam Hoover labels with pinned Git checks."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

COMMIT = '48018b62a245dd791e45d60b28068489a8c32742'
REPOSITORY = 'sraashis/deepdyn'


def download(destination, report):
    destination = Path(destination)
    tree_url = f'https://api.github.com/repos/{REPOSITORY}/git/trees/{COMMIT}?recursive=1'
    with urllib.request.urlopen(tree_url, timeout=90) as response:
        tree = json.load(response)
    wanted = [item for item in tree['tree'] if item['type'] == 'blob' and (
        item['path'].startswith('data/STARE/stare-images/') or
        item['path'].startswith('data/STARE/labels-ah/'))]
    images = [i for i in wanted if '/stare-images/' in i['path']]
    labels = [i for i in wanted if '/labels-ah/' in i['path']]
    if len(images) != 20 or len(labels) != 20:
        raise RuntimeError(f'Expected all 20 images and 20 labels, found {len(images)}, {len(labels)}')

    def one(item):
        relative = item['path'].removeprefix('data/STARE/')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/{item["path"]}'
        if target.exists():
            raw = target.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=90) as response:
                raw = response.read()
        git_sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if git_sha != item['sha']:
            raise RuntimeError('Pinned Git blob mismatch: ' + relative)
        target.write_bytes(raw)
        return dict(path=relative, url=url, bytes=len(raw), git_blob_sha1=git_sha,
                    sha256=hashlib.sha256(raw).hexdigest())

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, sorted(wanted, key=lambda item: item['path'])))
    receipt = dict(repository=REPOSITORY, commit=COMMIT, tree_url=tree_url,
                   complete_images=20, complete_annotations=20, files=records,
                   source='Pinned public copy in published research authors repository',
                   annotation='Adam Hoover', no_recovery_outcome_selection=True)
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    Path(report).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', default='work/stare')
    parser.add_argument('--report', default='results/research/eyeai_rebuild_oct15/data_acquisition.json')
    args = parser.parse_args()
    print(json.dumps({key: value for key, value in download(args.destination, args.report).items()
                      if key != 'files'}, indent=2))
