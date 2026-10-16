"""Reconcile contribution claims from final manifests and comparison ledgers.

This is a post-experiment structural/ledger audit, not a new execution benchmark.
It tests a sufficient easy-subclass condition, not computational hardness or
originality. No model payload is loaded and no historical measurement is changed.
"""
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import tarfile


def classify(manifest):
    nodes = {n['id']: n for n in manifest['nodes']}
    blobs = {n['blob'] for n in nodes.values()}
    roots = set(manifest['mandatory_blobs'])
    if not roots <= blobs:
        raise ValueError('Unknown mandatory root')
    optional = blobs - roots
    providers = Counter()
    edges = set()
    for node in nodes.values():
        if not node['replayable'] or node['blob'] in roots:
            continue
        providers[node['blob']] += 1
        for dependency in node['deps']:
            source = nodes[dependency]['blob']
            if source not in roots:
                edges.add((source, node['blob']))
    degree = dict.fromkeys(optional, 0)
    children = defaultdict(set)
    for source, target in edges:
        degree[target] += 1
        children[source].add(target)
    ready = deque(b for b in optional if not degree[b])
    visited = 0
    while ready:
        source = ready.popleft()
        visited += 1
        for target in children[source]:
            degree[target] -= 1
            if not degree[target]:
                ready.append(target)
    multiple = sorted(b for b, count in providers.items() if count > 1)
    acyclic = visited == len(optional)
    return dict(physical_artifacts=len(blobs), optional_artifacts=len(optional),
                multiple_producer_artifacts=len(multiple), physical_dag_after_fixing_roots=acyclic,
                sufficient_single_producer_dag=acyclic and not multiple,
                qualification='A false result only fails a sufficient condition; it is not evidence of hard optimization.')


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def comparison(rows, key_fields, exact='RecoverML_exact', baseline='robust_local'):
    grouped = defaultdict(dict)
    for row in rows:
        key = tuple(str(row[field]) for field in key_fields)
        if row['policy'] in grouped[key]:
            raise ValueError('Duplicate policy condition')
        grouped[key][row['policy']] = row
    results = []
    for key, methods in sorted(grouped.items()):
        ours, other = methods[exact], methods[baseline]
        results.append(dict(condition=list(key), exact_bytes=int(ours['retained_bytes']),
                            baseline_bytes=int(other['retained_bytes']),
                            tied=int(ours['retained_bytes']) == int(other['retained_bytes'])))
    return dict(conditions=len(results), ties=sum(r['tied'] for r in results),
                exact_lower_bytes=sum(r['exact_bytes'] < r['baseline_bytes'] for r in results),
                baseline_lower_bytes=sum(r['exact_bytes'] > r['baseline_bytes'] for r in results),
                rows=results)


def run(root, output):
    scientific = root / 'results/research/scientific_complete_oct16'
    retinal = root / 'results/research/eyeai_complete_oct15'
    letter = root / 'results/research/gigabyte_letter_oct16'
    records = []
    protocol = json.loads((scientific / 'protocol.json').read_text())
    expected = [f'{w}-{s}' for w, s in itertools.product(protocol['workflows'], protocol['seeds'])]
    with tarfile.open(scientific / 'captures.tar.gz', 'r:gz') as archive:
        for history in expected:
            manifest = json.load(archive.extractfile('captures/' + history + '/manifest.json'))
            records.append(dict(study='scientific', capture=history, **classify(manifest)))
    protocol = json.loads((retinal / 'protocol.json').read_text())
    expected = [f'{estimator}_s{seed}_v{versions}' for estimator, seed, versions in
                itertools.product(protocol['estimators'], protocol['seeds'], protocol['versions'])]
    for history in expected:
        manifest = json.loads((retinal / 'captures' / history / 'manifest.json').read_text())
        records.append(dict(study='retinal', capture=history, **classify(manifest)))
    records.append(dict(study='letter', capture='fixed_16_forests',
                        **classify(json.loads((letter / 'manifest.json').read_text()))))
    groups = {study: dict(captures=sum(r['study'] == study for r in records),
                         sufficient_single_producer_dag=sum(r['study'] == study and r['sufficient_single_producer_dag'] for r in records))
              for study in ('scientific', 'retinal', 'letter')}
    science_rows = [r for r in read_csv(scientific / 'summary.csv') if float(r['budget_fraction']) == 1.0]
    if any(r['complete'] != 'True' for r in science_rows if r['policy'] in ('RecoverML_exact', 'robust_local')):
        raise ValueError('Unexpected incomplete full-budget exact/local case')
    science = comparison(science_rows, ('case',))
    retina_rows = read_csv(retinal / 'summary.csv')
    if any(int(r['exact']) != int(r['requests']) for r in retina_rows):
        raise ValueError('Retinal comparison includes an incomplete policy')
    retina = comparison(retina_rows, ('capture_id', 'target_mode', 'availability'))
    greedy = comparison(retina_rows, ('capture_id', 'target_mode', 'availability'), baseline='robust_greedy')
    large_rows = read_csv(letter / 'summary.csv')
    if any(r['allowed_exact'] != r['allowed_requests'] for r in large_rows if r['policy'] in ('RecoverML_exact', 'robust_local')):
        raise ValueError('Large exact/local comparison includes partial coverage')
    large = comparison(large_rows, ('scope',))
    numeric = json.loads((letter / 'analysis.json').read_text())
    preprocessing = numeric['scopes']['preprocessing']
    if preprocessing['saving_bytes'] != preprocessing['snapshot_bytes'] - preprocessing['exact_bytes']:
        raise ValueError('Canonical storage arithmetic differs')
    checks = dict(scientific_conditions=science['conditions'] == 48, retinal_conditions=retina['conditions'] == 108,
                  letter_scopes=large['conditions'] == 2,
                  comparisons_reconcile=all(v['ties'] == v['conditions'] for v in (science, retina, large)))
    source_paths = [scientific / name for name in ('captures.tar.gz', 'summary.csv')]
    source_paths += [retinal / 'summary.csv', letter / 'summary.csv', letter / 'manifest.json', letter / 'analysis.json']
    source_paths += [scientific / 'protocol.json', retinal / 'protocol.json']
    source_paths += [retinal / 'captures' / history / 'manifest.json' for history in expected]
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip()
    git_hashes, working_hashes, newline_conversions = {}, {}, []
    for path in source_paths:
        name = path.relative_to(root).as_posix()
        recorded = subprocess.check_output(['git', '-C', str(root), 'show', commit + ':' + name])
        working = path.read_bytes()
        if working != recorded:
            if path.suffix not in ('.json', '.csv') or working.replace(b'\r\n', b'\n') != recorded.replace(b'\r\n', b'\n'):
                raise ValueError('Analysis input differs from recorded Git source: ' + name)
            newline_conversions.append(name)
        git_hashes[name] = hashlib.sha256(recorded).hexdigest()
        working_hashes[name] = hashlib.sha256(working).hexdigest()
    result = dict(schema=1, status='PASS' if all(checks.values()) else 'FAIL',
                  source_commit=commit,
                  checks=checks, topology_summary=groups, topology_records=records,
                  scientific_full_budget=science, retinal_full_contract=retina,
                  retinal_simple_greedy=greedy, letter_full_contract=large,
                  letter_storage=preprocessing, broad_saving_bytes=numeric['scopes']['broad']['saving_bytes'],
                  source_sha256_git=git_hashes, source_sha256_working_tree=working_hashes,
                  checkout_newline_conversions_only=newline_conversions,
                  scope='Post-run structural and comparison-ledger audit. Conditions are correlated, not independent workflow samples. No model execution, new timings, or novelty proof.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'], topology=groups,
                          scientific_ties=science['ties'], retinal_ties=retina['ties'], letter_ties=large['ties'])))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(Path(__file__).resolve().parents[1], args.output))
