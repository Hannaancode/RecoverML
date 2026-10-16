"""Audit all fixed cloud seed blocks without executing captured model payloads.

The per-block audit checks actual request identities, grounded outcomes and
integer flow certificates. This additional audit checks completeness across
blocks, source snapshots, shared-capture identity and summary/plan cross-links.
It does not constitute human peer review or proof of general research novelty.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import tarfile

from analyze_multiview_followup import audit


SEEDS = (20261016, 20261017, 20261018)
METHODS = {'RecoverML_exact', 'scenario_exact', 'robust_greedy', 'robust_local',
           'manual_best_frontier', 'HYPPO_rank', 'HYPPO_frequency', 'HELIX_rule', 'target_snapshots'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fixed_grid(config, seed, shared):
    require(config['seeds'] == [seed], 'Wrong or incomplete seed block')
    require(config['datasets'] == ['wine', 'breast_cancer'], 'Dataset grid changed')
    require(config['versions'] == [4, 16, 64], 'Version grid changed')
    require(config['concat_materialized'] == [False, True], 'Concat controls missing')
    require(len(config['methods']) == 9 and set(config['methods']) == METHODS, 'Method grid changed')
    require(config['maximum_lost_groups'] == 1 and config['timing_repetitions'] == 3,
            'Failure bound or repetitions changed')
    require(bool(config.get('capture_input')) == shared, 'Wrong loss grouping')


def source_snapshot(directory, source_commit, root):
    start = json.loads((directory / 'run_start.json').read_bytes())
    end = json.loads((directory / 'run_end.json').read_bytes())
    require(start['commit'] == source_commit, 'Unexpected execution source commit')
    require(start['source_sha256'] == end['source_sha256'], 'Source receipt changed')
    require(start['protocol_sha256'] == sha((directory / 'protocol.json').read_bytes()), 'Protocol changed')
    with tarfile.open(directory / 'source_snapshot.tar.gz') as archive:
        members = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    expected_names = {name.lstrip('/') for name in start['source_sha256']}
    require(set(members) == expected_names, 'Source snapshot inventory differs')
    for name, expected in start['source_sha256'].items():
        raw = members[name.lstrip('/')]
        require(sha(raw) == expected, 'Archived source hash differs: ' + name)
        if name.startswith('src/recoverml/'):
            committed = subprocess.check_output(['git', '-C', str(root), 'show', source_commit + ':' + name])
            require(raw == committed, 'Runtime source differs from pinned commit: ' + name)
        elif '/scripts/' in name or name.startswith('scripts/'):
            relative = 'scripts/' + name.rsplit('/scripts/', 1)[-1].removeprefix('scripts/')
            committed = subprocess.check_output(['git', '-C', str(root), 'show', source_commit + ':' + relative])
            require(raw == committed, 'Runner differs from pinned commit')
        else:
            require(raw == (directory / 'protocol.json').read_bytes(), 'Archived protocol differs')
    return len(members)


def plan_crosslinks(directory):
    with (directory / 'summary.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    plans = json.loads(gzip.decompress((directory / 'planner_records.json.gz').read_bytes()))
    grouped = defaultdict(list)
    for plan in plans:
        require(math.isfinite(plan['planning_s']) and plan['planning_s'] >= 0, 'Invalid planner duration')
        grouped[(plan['history'], plan['method'])].append(plan)
    indexed = {(row['history'], row['method']): row for row in rows}
    for key, row in indexed.items():
        history, method = key
        ours = indexed[(history, 'RecoverML_exact')]
        require(int(row['exact_minimum_bytes']) == int(ours['retained_bytes']), 'Optimum summary link differs')
        require(float(row['planning_median_s']) == statistics.median(p['planning_s'] for p in grouped[key]),
                'Planner median differs from raw calls')
        require(all(p['retained_bytes'] == int(row['retained_bytes']) for p in grouped[key]),
                'Planner/summary byte link differs')
        if method in ('RecoverML_exact', 'scenario_exact', 'robust_greedy', 'robust_local',
                      'manual_best_frontier', 'target_snapshots'):
            require(row['fully_recoverable'] == 'True' and int(row['expected_blocked']) == 0,
                    'A full-contract baseline is not fully recoverable')
    by_store = defaultdict(set)
    for row in rows:
        by_store[(row['history'], row['store_key'])].add(row['method'])
    with gzip.open(directory / 'execution_traces.jsonl.gz', 'rt') as stream:
        for line in stream:
            record = json.loads(line)
            require(len(record['methods']) == len(set(record['methods'])) and
                    set(record['methods']) == by_store[(record['history'], record['store_key'])],
                    'Shared execution is attributed to the wrong methods')


def capture_members(directory):
    with tarfile.open(directory / 'captures.tar.gz') as archive:
        return {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}


def artifact_receipt(block, seed, source_commit):
    receipt = json.loads((block / 'artifact_receipt.json').read_bytes())
    artifact = receipt['artifact']
    require(artifact['name'] == 'strongest-baseline-seed-' + str(seed), 'Artifact seed differs')
    require(artifact['workflow_run']['head_sha'] == source_commit, 'Artifact source differs')
    require(artifact['workflow_run']['id'] == 38945172079, 'Unexpected cloud run')
    require('sha256:' + receipt['original_zip_sha256'] == artifact['digest'], 'ZIP digest receipt differs')
    packed = {}
    for phase in ('separate', 'shared'):
        for filename in ('captures.tar.gz', 'case_receipts.tar.gz'):
            with tarfile.open(block / phase / filename) as archive:
                members = [m for m in archive if m.isfile()]
                require(len(members) == len({m.name for m in members}), 'Duplicate transport archive member')
                for member in members:
                    path = phase + '/' + member.name
                    require(path not in packed, 'Repeated packed evidence')
                    packed[path] = archive.extractfile(member).read()
    expected_packed = {path for path in receipt['files'] if '/captures/' in path or '/cases/' in path}
    require(set(packed) == expected_packed, 'Packed evidence inventory differs from original ZIP')
    for path, item in receipt['files'].items():
        require(not Path(path).is_absolute() and '..' not in Path(path).parts and ':' not in path and '\\' not in path,
                'Unsafe artifact receipt path')
        raw = packed[path] if path in packed else (block / path).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Artifact member differs: ' + path)
    return dict(artifact_id=artifact['id'], original_zip_sha256=receipt['original_zip_sha256'],
                checked_original_members=len(receipt['files']))


def summarize(comparisons):
    counts = Counter('win' if r['saved_vs_local'] > 0 else 'tie' if r['saved_vs_local'] == 0 else 'loss'
                     for r in comparisons)
    return dict(histories=len(comparisons), local_comparison=dict(counts),
                maximum_percent_saved_vs_local=max(r['percent_vs_local'] for r in comparisons),
                median_percent_saved_vs_local=statistics.median(r['percent_vs_local'] for r in comparisons),
                manual_frontier_ties=sum(r['our_bytes'] == r['manual_bytes'] for r in comparisons),
                manual_frontier_wins=sum(r['our_bytes'] < r['manual_bytes'] for r in comparisons),
                manual_frontier_losses=sum(r['our_bytes'] > r['manual_bytes'] for r in comparisons),
                median_planning_speedup_vs_local=statistics.median(r['planning_speedup_vs_local'] for r in comparisons),
                median_planning_speedup_vs_scenario=statistics.median(r['planning_speedup_vs_scenario'] for r in comparisons))


def old_timing(directory, source_commit, root):
    report = json.loads((directory / 'report.json').read_bytes())
    start = json.loads((directory / 'run_start.json').read_bytes())
    protocol = json.loads((directory / 'protocol.json').read_bytes())
    require(protocol['repetitions'] == 5 and protocol['metadata_only'] is True,
            'Old-condition timing scope changed')
    require(report['status'] == 'PASS' and not report['source_changed'], 'Timing did not finish cleanly')
    require(start['capture_archive_sha256'] == sha(subprocess.check_output(['git', '-C', str(root), 'show',
        source_commit + ':results/research/scientific_complete_oct16/captures.tar.gz'])), 'Frozen capture archive differs')
    for name, expected in start['source_sha256'].items():
        relative = name if name.startswith('src/recoverml/') else 'scripts/' + name.rsplit('/', 1)[-1]
        require(sha(subprocess.check_output(['git', '-C', str(root), 'show', source_commit + ':' + relative])) == expected,
                'Timing source differs from pinned commit')
    original = json.loads(gzip.decompress(subprocess.check_output(['git', '-C', str(root), 'show',
        source_commit + ':results/research/scientific_complete_oct16/planner_records.json.gz'])))
    expected = {r['case']: r['actual_bytes'] for r in original
                if r['policy'] == 'RecoverML_exact' and 'budget_fraction' not in r}
    require(len(expected) == 48, 'Original condition grid differs')
    results = report['results']
    require(Counter(r['case'] for r in results) == Counter({case: 1 for case in expected}), 'Timing condition grid differs')
    calls = json.loads(gzip.decompress((directory / 'planner_calls.json.gz').read_bytes()))
    methods = ('RecoverML_auto', 'scenario_exact', 'robust_local')
    require(Counter((r['case'], r['method'], r['repetition']) for r in calls) ==
            Counter({(case, method, rep): 1 for case in expected for method in methods for rep in range(5)}),
            'Timing call identities differ')
    grouped = defaultdict(list)
    for record in calls:
        require(math.isfinite(record['planning_s']) and record['planning_s'] >= 0, 'Invalid timing')
        require(record['diagnostic']['robust_certified'], 'Uncertified timing store')
        if record['method'] != 'robust_local':
            require(record['status'] == 'ok' and record['diagnostic']['storage_optimal'] and
                    record['retained_bytes'] == expected[record['case']], 'Timing exact result differs')
        grouped[(record['case'], record['method'])].append(record)
    for result in results:
        require(result['original_minimum'] == expected[result['case']], 'Timing optimum link differs')
        for method in methods:
            records = grouped[(result['case'], method)]
            require(result['median_s'][method] == statistics.median(r['planning_s'] for r in records), 'Timing median differs')
            require(all(result['sizes'][method] == r['retained_bytes'] for r in records), 'Timing byte summary differs')
        for suffix, method in [('local', 'robust_local'), ('scenario', 'scenario_exact')]:
            require(result['speedup_vs_' + suffix] == result['median_s'][method] / result['median_s']['RecoverML_auto'],
                    'Timing speedup differs')
    summary = {}
    for label, selected in [('all', results), ('dag', [r for r in results if r['dag_eligible']]),
                            ('general_fallback', [r for r in results if not r['dag_eligible']])]:
        summary[label] = dict(conditions=len(selected), faster_than_local=sum(r['speedup_vs_local'] > 1 for r in selected),
            median_speedup_vs_local=statistics.median(r['speedup_vs_local'] for r in selected),
            median_speedup_vs_scenario=statistics.median(r['speedup_vs_scenario'] for r in selected))
    return dict(status='PASS', conditions=48, calls=len(calls), summary=summary,
                scope='Metadata-only paired timing of existing conditions, not model recovery speed')


def run(directory, source_commit, root):
    require(len(source_commit) == 40, 'Full source commit required')
    phases = {name: dict(blocks=[], comparisons=[], runtime=Counter()) for name in ('separate', 'shared')}
    inputs = {}
    artifacts = []
    for seed in SEEDS:
        block = directory / ('seed' + str(seed))
        artifacts.append(artifact_receipt(block, seed, source_commit))
        inputs[('seed' + str(seed)) + '/artifact_receipt.json'] = sha((block / 'artifact_receipt.json').read_bytes())
        require((block / 'cloud_metadata/commit.txt').read_text().strip() == source_commit, 'Runner commit differs')
        for name in phases:
            case = block / name
            fixed_grid(json.loads((case / 'protocol.json').read_bytes()), seed, name == 'shared')
            sources = source_snapshot(case, source_commit, root)
            original_audit = (case / 'independent_audit.json').read_bytes()
            previous = json.loads(original_audit)
            try:
                checked = audit(case)
            finally:
                # The legacy analyzer writes a report. Preserve its original
                # runner bytes even on Windows or if an audit raises midway.
                (case / 'independent_audit.json').write_bytes(original_audit)
            require(previous == checked, 'Fresh block audit differs from published runner audit')
            require((checked['histories'], checked['conditions'], checked['planning_calls'], checked['checked_flow_proofs'])
                    == (12, 108, 324, 36), 'Incomplete closed block')
            plan_crosslinks(case)
            phases[name]['comparisons'].extend(checked['comparisons'])
            phases[name]['runtime'].update(checked['actual_runtime'])
            phases[name]['blocks'].append(dict(seed=seed, histories=12, conditions=108, planning_calls=324,
                checked_flow_proofs=36, checked_source_files=sources, actual_runtime=checked['actual_runtime']))
            print(json.dumps(dict(verified_seed=seed, phase=name, status='PASS')), flush=True)
            for path in case.iterdir():
                if path.is_file():
                    inputs[path.relative_to(directory).as_posix()] = sha(path.read_bytes())
        original = capture_members(block / 'separate')
        shared = capture_members(block / 'shared')
        require(set(original) == set(shared), 'Paired capture inventories differ')
        for path in original:
            if not path.endswith('/info.json'):
                require(original[path] == shared[path], 'Paired physical capture changed: ' + path)
            else:
                first, second = json.loads(original[path]), json.loads(shared[path])
                require(all(second.get(k) == v for k, v in first.items()), 'Paired capture metadata changed')
    for phase in phases.values():
        phase['runtime'] = dict(phase['runtime'])
        phase['summary'] = summarize(phase['comparisons'])
        phase['by_capture_boundary'] = {
            'concat' if concat else 'fused': summarize([r for r in phase['comparisons'] if r['concat_materialized'] == concat])
            for concat in (False, True)}
    timing = old_timing(directory / 'seed20261016/dag_timing', source_commit, root)
    for path in (directory / 'seed20261016/dag_timing').iterdir():
        if path.is_file():
            inputs[path.relative_to(directory).as_posix()] = sha(path.read_bytes())
    return dict(schema=1, status='PASS', source_commit=source_commit, seeds=list(SEEDS), phases=phases,
                artifacts=artifacts, old_condition_timing=timing,
                checked_input_sha256=inputs,
                scope='Fresh cloud executions of the complete fixed exploratory grid, with post-run metadata and raw-log verification. '
                      'No model payload is loaded by this audit. No new native DVC execution or external human review.',
                inference='A gap versus the specified one-add local heuristic does not imply superiority over all heuristics. '
                          'A manual frontier matching the certified optimum cannot be beaten in retained bytes under this contract.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refuse to overwrite an existing audit')
    report = run(args.directory, args.source_commit, Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({name: phase['summary'] for name, phase in report['phases'].items()}, indent=2))
