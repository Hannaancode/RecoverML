"""Audit committed release bytes without loading model payloads or rerunning studies.

Git object bytes avoid false failures from Windows checkout newline conversion.
An available-file check can pass while the original evidence release is incomplete.
No missing historical file, timing, certificate, or archive is reconstructed.
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path, PurePosixPath
import subprocess


CHECKSUM_FILES = {'CHECKSUMS.json', 'CHECKSUMS_GITHUB.json'}
SCIENTIFIC = 'results/research/scientific_complete_oct16'
RETINAL = 'results/research/eyeai_complete_oct15'
LARGE = 'results/research/gigabyte_letter_oct16'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Snapshot:
    def __init__(self, root, ref='HEAD'):
        self.root = Path(root)
        def git(*args, **kwargs):
            return subprocess.check_output(['git', '-C', str(self.root), *args], **kwargs)
        self.tree = git('write-tree').decode().strip() if ref == 'INDEX' else git('rev-parse', ref + '^{tree}').decode().strip()
        self.files = {}
        entries = []
        for item in git('ls-tree', '-r', '-z', self.tree).split(b'\0'):
            if not item:
                continue
            head, path = item.split(b'\t', 1)
            mode, kind, oid = head.split()
            if kind != b'blob' or mode not in (b'100644', b'100755'):
                raise ValueError('Only regular tracked files are supported: ' + path.decode())
            entries.append((path.decode(), oid.decode()))
        objects = list(dict.fromkeys(oid for _, oid in entries))
        raw = git('cat-file', '--batch', input=('\n'.join(objects) + '\n').encode())
        content, offset = {}, 0
        for oid in objects:
            end = raw.index(b'\n', offset)
            actual, kind, length = raw[offset:end].split()
            if actual.decode() != oid or kind != b'blob':
                raise ValueError('Unexpected Git batch response')
            size = int(length)
            content[oid] = raw[end + 1:end + 1 + size]
            offset = end + 2 + size
        self.files = {path: content[oid] for path, oid in entries}

    def json(self, path):
        return json.loads(self.files[path])

    def csv(self, path):
        return list(csv.DictReader(io.StringIO(self.files[path].decode())))

    def raw(self, path):
        with gzip.GzipFile(fileobj=io.BytesIO(self.files[path])) as stream:
            return [json.loads(line) for line in stream if line.strip()]


def checksum_audit(snapshot):
    expected = {p: sha(data) for p, data in snapshot.files.items() if p not in CHECKSUM_FILES}
    result = {}
    for name in sorted(CHECKSUM_FILES):
        if name not in snapshot.files:
            result[name] = dict(status='MISSING')
            continue
        manifest = snapshot.json(name)
        missing = sorted(set(manifest) - set(expected))
        changed = sorted(p for p in set(manifest) & set(expected) if manifest[p] != expected[p])
        unlisted = sorted(set(expected) - set(manifest))
        result[name] = dict(status='PASS' if not (missing or changed or unlisted) else 'FAIL',
                            listed=len(manifest), missing=missing, changed=changed, unlisted=unlisted)
    return result


def evidence_inventory(snapshot):
    required = {}
    for line in snapshot.files[SCIENTIFIC + '/SHA256SUMS'].decode().splitlines():
        digest, relative = line.split(None, 1)
        if PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts:
            raise ValueError('Unsafe evidence path')
        required[SCIENTIFIC + '/' + relative] = digest
    for stem, item in snapshot.json(RETINAL + '/ledger_compression.json').items():
        required[RETINAL + '/' + stem + '.gz'] = item['compressed_sha256']
    required[RETINAL + '/stores_deduplicated.tar.gz'] = snapshot.json(RETINAL + '/store_compaction.json')['archive_sha256']
    required[LARGE + '/selected_frontier.tar.gz'] = snapshot.json(LARGE + '/store_membership.json')['frontier_archive_sha256']
    missing = sorted(p for p in required if p not in snapshot.files)
    mismatches = sorted(p for p, digest in required.items() if p in snapshot.files and sha(snapshot.files[p]) != digest)
    additional = [RETINAL + '/interrupted_attempt_evidence.tar.gz']
    missing_unhashed = [p for p in additional if p not in snapshot.files]
    return dict(status='COMPLETE' if not (missing or mismatches or missing_unhashed) else 'INCOMPLETE',
                required=len(required), present=len(required)-len(missing),
                missing=missing, hash_mismatches=mismatches, expected_sha256=required,
                additional_required_without_recorded_hash=additional, missing_without_recorded_hash=missing_unhashed)


def scientific_audit(snapshot):
    prefix = SCIENTIFIC + '/'
    rows = snapshot.raw(prefix + 'execution_traces.jsonl.gz')
    protocol = snapshot.json(prefix + 'protocol.json')
    report = snapshot.json(prefix + 'report.json')
    headline = snapshot.json(prefix + 'headline_counters.json')['methods']
    errors, identities, counts, conditions = [], set(), Counter(), {}
    expected_conditions = set(itertools.product(
        (f'{w}-{s}-{scope}-k{k}' for w, s, scope, k in itertools.product(
            protocol['workflows'], protocol['seeds'], protocol['capability_scopes'], protocol['loss_bounds'])),
        protocol['methods'], protocol['optional_snapshot_budget_fractions']))
    for row in rows:
        condition = row['case'], row['policy'], float(row['budget_fraction'])
        identity = condition + (str(row['version']), tuple(row['disabled']))
        if identity in identities:
            errors.append('Duplicate scientific raw request')
        identities.add(identity)
        counter = conditions.setdefault(condition, Counter())
        counter['requests'] += 1
        for field in ('exact', 'expected_blocked', 'unexpected'):
            counter[field] += int(row[field])
            counts[field] += int(row[field])
        if sum(bool(row[f]) for f in ('exact', 'expected_blocked', 'unexpected')) != 1:
            errors.append('Invalid scientific outcome partition')
        if not row['capture_archive_absent'] or row['end_timestamp_ns'] < row['start_timestamp_ns'] or row['latency_s'] < 0:
            errors.append('Invalid scientific archive or timing assertion')
    if set(conditions) != expected_conditions:
        errors.append('Scientific condition grid differs from frozen protocol')
    if len(rows) != report['requests'] or len(conditions) != report['case_policy_budget_rows']:
        errors.append('Scientific report denominators differ')
    for field in ('exact', 'expected_blocked', 'unexpected'):
        if counts[field] != report[field]:
            errors.append('Scientific report outcome differs: ' + field)
    for method, declared in headline.items():
        matched = [c for key, c in conditions.items() if key[1] == method]
        actual = dict(exact=sum(c['exact'] for c in matched), requests=sum(c['requests'] for c in matched),
                      complete_conditions=sum(c['exact'] == c['requests'] for c in matched), conditions=len(matched))
        if actual != declared:
            errors.append('Scientific headline differs: ' + method)
    if sha(snapshot.files[prefix + 'execution_traces.jsonl.gz']) != report['raw_trace_sha256']:
        errors.append('Scientific raw hash differs')
    return dict(status='PASS' if not errors else 'FAIL', errors=sorted(set(errors)),
                requests=len(rows), conditions=len(conditions), outcomes=dict(counts),
                limitation='Raw identities, frozen condition grid, report and headline reconciliation only. Missing capture/planner archives prevent the original full manifest-derived audit.')


def retinal_audit(snapshot):
    prefix = RETINAL + '/'
    rows = snapshot.csv(prefix + 'summary.csv')
    raw = snapshot.raw(prefix + 'raw.jsonl.gz')
    protocol = snapshot.json(prefix + 'protocol.json')
    errors, seen, counters = [], set(), {}
    fault_sets = {'intact': [()], 'legacy_removed': [(), ('legacy_extractor',)],
                  'training_prediction_removed': [(), ('retina_predict',), ('retina_train',), ('retina_predict', 'retina_train')]}
    expected = {(r['condition_id'], f, str(v)) for r in rows for f in fault_sets[r['availability']] for v in range(int(r['versions']))}
    for row in raw:
        identity = row['condition_id'], tuple(row['fault']), str(row['version'])
        if identity in seen:
            errors.append('Duplicate retinal raw request')
        seen.add(identity)
        counter = counters.setdefault(row['condition_id'], Counter())
        counter['requests'] += 1
        counter['exact'] += int(bool(row['exact']) and row['actual_sha256'] == row['expected_sha256'])
        counter['errors'] += int(row['error'] is not None)
    fields = ('estimator', 'seed', 'versions', 'target_mode', 'availability', 'policy')
    expected_conditions = set(itertools.product(protocol['estimators'], map(str, protocol['seeds']),
        map(str, protocol['versions']), protocol['targets'], protocol['availability'], protocol['policies']))
    actual_conditions = [tuple(r[f] for f in fields) for r in rows]
    if len(set(actual_conditions)) != len(rows) or set(actual_conditions) != expected_conditions:
        errors.append('Retinal summary grid differs')
    if seen != expected or len(raw) != protocol['expected_recovery_requests']:
        errors.append('Retinal raw grid differs')
    for row in rows:
        if any(int(row[f]) != counters.get(row['condition_id'], {}).get(f) for f in ('requests', 'exact', 'errors')):
            errors.append('Retinal raw/summary counts differ')
    commands = snapshot.json(prefix + 'native_commands.json')
    checkouts = [r for r in commands if r['command'][1:4] == ['-m', 'dvc', 'checkout']]
    if len(checkouts) != 624 or any(r['returncode'] for r in commands):
        errors.append('Retinal native checkout receipts differ')
    return dict(status='PASS' if not errors else 'FAIL', errors=sorted(set(errors)), summary_rows=len(rows),
                requests=len(raw), exact=sum(c['exact'] for c in counters.values()), native_checkouts=len(checkouts),
                limitation='Recorded target hashes and receipts are reconciled; original model execution is not repeated.')


def source_audit(snapshot):
    receipt = snapshot.json(LARGE + '/source_snapshot_receipt.json')
    rows = receipt['sources']
    errors = [r['saved_path'] for r in rows if r['saved_path'] not in snapshot.files or sha(snapshot.files[r['saved_path']]) != r['expected_sha256']]
    return dict(status='PASS' if not errors else 'FAIL', checked=len(rows), errors=errors)


def audit(snapshot):
    checksums = checksum_audit(snapshot)
    inventory = evidence_inventory(snapshot)
    scientific = scientific_audit(snapshot)
    retinal = retinal_audit(snapshot)
    sources = source_audit(snapshot)
    return dict(schema=1, git_tree=snapshot.tree,
                scope='Committed byte identity and published ledger reconciliation; no model replay, benchmark rerun, or external peer review.',
                available_evidence_checks='PASS' if scientific['status'] == retinal['status'] == sources['status'] == 'PASS' and not inventory['hash_mismatches'] else 'FAIL',
                release_complete=inventory['status'] == 'COMPLETE' and all(x['status'] == 'PASS' for x in checksums.values()),
                tracked_regular_files=len(snapshot.files), checksums=checksums, required_evidence=inventory,
                scientific=scientific, retinal=retinal, large_frozen_sources=sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD', help='Committed ref or INDEX for the staged tree')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--refresh-checksums', action='store_true')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    snapshot = Snapshot(root, args.ref)
    if args.refresh_checksums:
        checksums = {p: sha(data) for p, data in sorted(snapshot.files.items()) if p not in CHECKSUM_FILES}
        for name in sorted(CHECKSUM_FILES):
            (root / name).write_text(json.dumps(checksums, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(dict(ref=args.ref, files=len(checksums), refreshed=sorted(CHECKSUM_FILES))))
        return 0
    result = audit(snapshot)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps({k: result[k] for k in ('git_tree', 'available_evidence_checks', 'release_complete', 'tracked_regular_files')}))
    checksums_ok = all(c['status'] == 'PASS' for c in result['checksums'].values())
    return 1 if result['available_evidence_checks'] != 'PASS' or not checksums_ok or (args.require_complete and not result['release_complete']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
