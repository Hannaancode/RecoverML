"""Audit all five fixed groups and their original GitHub artifact ZIP members."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from audit_planner_efficiency import audit, require


GROUPS = {'scientific', 'cloud', 'retinal', 'letter', 'scaling'}


def release(directory):
    receipts = directory / 'receipts'
    require({p.stem for p in receipts.glob('*.json')} == GROUPS, 'All five original artifact receipts required')
    results = {}
    source = set()
    checked = 0
    artifacts = []
    for group in sorted(GROUPS):
        record = json.loads((receipts / (group + '.json')).read_bytes())
        artifact = record['artifact']
        require(artifact['name'] == 'planner-efficiency-' + group, 'Artifact group differs')
        path = directory / 'github_artifacts' / (artifact['name'] + '.zip')
        require('sha256:' + hashlib.sha256(path.read_bytes()).hexdigest() == artifact['digest'],
                'Original GitHub artifact ZIP digest differs')
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)) and set(names) == set(record['files']),
                    'Original ZIP inventory differs')
            for name in names:
                relative = PurePosixPath(name)
                require(not relative.is_absolute() and '..' not in relative.parts and
                        ':' not in name and '\\' not in name, 'Unsafe artifact member')
                raw = archive.read(name)
                info = record['files'][name]
                require(len(raw) == info['bytes'] and hashlib.sha256(raw).hexdigest() == info['sha256']
                        and raw == directory.joinpath(group, *relative.parts).read_bytes(),
                        'Original artifact member differs')
                checked += 1
        result = audit(directory / group / 'planner_comparison')
        require(result['group'] == group and result['source_commit'] == artifact['workflow_run']['head_sha'],
                'Artifact/source link differs')
        original = json.loads((directory / group / 'audit.json').read_bytes())
        require(original == result, 'Recreated audit differs from original runner audit')
        source.add(result['source_commit'])
        results[group] = result
        artifacts.append(dict(id=artifact['id'], name=artifact['name'], digest=artifact['digest']))
    require(len(source) == 1, 'Groups used different source revisions')
    return dict(status='PASS', source_commit=source.pop(), original_artifact_members_checked=checked,
        frozen_conditions=sum(results[g]['conditions'] for g in GROUPS - {'scaling'}),
        scaling_conditions=results['scaling']['conditions'],
        total_timing_calls=sum(r['timing_calls'] for r in results.values()),
        declared_loss_closure_checks=sum(r['declared_loss_closure_checks'] for r in results.values()),
        artifacts=artifacts, groups=results,
        qualification='All fixed metadata-only groups and original artifact bytes reconciled. No new model payload replay or universal dominance claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = release(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'source_commit', 'frozen_conditions', 'scaling_conditions', 'total_timing_calls', 'declared_loss_closure_checks')}, indent=2))
