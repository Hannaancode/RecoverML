"""Reconcile the full fixed planner follow-up without loading model payloads."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import subprocess

from benchmark_planner_efficiency import ROOT, SOURCES, frozen, stress
from recoverml.core import canonical, digest
from recoverml.capability_retention import retained_bytes, restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identities(calls, cases, methods, repetitions):
    expected = Counter({(c, m, r): 1 for c, m, r in itertools.product(cases, methods, range(repetitions))})
    require(Counter((r['case'], r['method'], r['repetition']) for r in calls) == expected,
            'Missing, duplicate or replaced timing identity')


def audit(directory):
    start = json.loads((directory / 'run_start.json').read_bytes())
    report = json.loads((directory / 'report.json').read_bytes())
    config, group = start['protocol'], start['group']
    fixed = json.loads((ROOT / 'configs/planner_efficiency_oct26.json').read_bytes())
    require(config == fixed, 'Fixed comparison protocol differs')
    require(report['group'] == group and report['status'] == 'PASS' and not report['source_changed'],
            'Incomplete or failed comparison')
    require(set(start['source_sha256']) == set(SOURCES), 'Benchmark source inventory differs')
    for path, expected in start['source_sha256'].items():
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', start['commit'] + ':' + path])
        require(digest(raw) == expected, 'Pinned benchmark source differs: ' + path)
    for path, expected in start['reference_source_sha256'].items():
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', config['reference_commit'] + ':' + path])
        require(digest(raw) == expected, 'Pinned reference source differs')
    inputs = {}
    if group == 'scaling':
        cases = [(topology + '-w' + str(width) + '-s' + str(seed), *stress(topology, width, seed))
                 for topology, width, seed in itertools.product(config['scaling_topologies'],
                        config['scaling_widths'], config['scaling_seeds'])]
        methods = config['scaling_methods']
    else:
        cases = list(frozen(group, inputs))
        methods = config['methods']
    require(inputs == report['input_sha256'], 'Frozen input inventory or bytes differ')
    require(len(cases) == report['conditions'] == config['groups'][group], 'Fixed condition count differs')
    rows = {r['case']: r for r in report['comparisons']}
    require(len(rows) == len(report['comparisons']) == len(cases) and set(rows) == {c[0] for c in cases},
            'Incomplete or replaced report grid')
    for name in ('calls', 'selections'):
        require(digest((directory / (name + '.json.gz')).read_bytes()) == report[name + '_sha256'],
                'Closed evidence hash differs')
    calls = json.loads(gzip.decompress((directory / 'calls.json.gz').read_bytes()))
    selections = json.loads(gzip.decompress((directory / 'selections.json.gz').read_bytes()))
    require(all(digest(canonical(blobs)) == key and len(blobs) == len(set(blobs))
                for key, blobs in selections.items()), 'Retained-set identity differs')
    identities(calls, rows, methods, config['repetitions'])
    require(report['calls'] == len(calls), 'Call total differs')
    require(set(selections) == {c['selected_sha256'] for c in calls}, 'Unlinked retained sets')
    closure_checks = 0
    for case, g, caps, k, expected in cases:
        row = rows[case]
        require(row['expected_bytes'] == expected and row['nodes'] == len(g.nodes) and
                row['versions'] == len(g.targets), 'Condition metadata differs')
        relevant = [r for r in calls if r['case'] == case]
        for record in relevant:
            require(all(math.isfinite(record[key]) and record[key] >= 0 for key in ('elapsed_s', 'cpu_s')),
                    'Invalid planner timing')
            selected = set(selections[record['selected_sha256']])
            require(g.roots <= selected <= g.candidates, 'Invalid retained set')
            require(retained_bytes(g, selected, caps, k) == record['retained_bytes'], 'Paid bytes differ')
            if record['method'] != 'robust_local':
                require(record['status'] == 'ok' and record['storage_optimal'] and
                        record['retained_bytes'] == expected, 'Frozen exact optimum differs')
            require(record['robust_certified'], 'Uncertified record')
            for loss in fault_sets(caps, k):
                require(certificate(restricted(g, caps, loss), selected)['complete'], 'Selected store is not robust')
                closure_checks += 1
        for rep in range(config['repetitions']):
            order = list(methods)
            random.Random(group + '/' + case + '/' + str(rep)).shuffle(order)
            require(sorted((r['order'], r['method']) for r in relevant if r['repetition'] == rep)
                    == list(enumerate(order)), 'Declared paired order differs')
        for method in methods:
            measured = [r for r in relevant if r['method'] == method]
            median = statistics.median(r['elapsed_s'] for r in measured)
            require(row['median_s'][method] == median and
                    all(r['retained_bytes'] == row['sizes'][method] for r in measured), 'Raw/summary links differ')
            if method != 'RecoverML_indexed':
                require(row['paired_speedup'][method] == median / row['median_s']['RecoverML_indexed'],
                        'Paired speedup differs')
    expected_summary = {}
    for method in methods:
        if method == 'RecoverML_indexed':
            continue
        values = [r['paired_speedup'][method] for r in rows.values()]
        expected_summary[method] = dict(cases=len(rows), indexed_faster=sum(v > 1 for v in values),
            indexed_slower=sum(v < 1 for v in values), median_paired_speedup=statistics.median(values),
            minimum_paired_speedup=min(values), maximum_paired_speedup=max(values),
            storage_wins=sum(r['sizes'][method] > r['expected_bytes'] for r in rows.values()),
            storage_ties=sum(r['sizes'][method] == r['expected_bytes'] for r in rows.values()))
    require(report['summary'] == expected_summary, 'Full-grid summary differs')
    return dict(status='PASS', group=group, source_commit=start['commit'], conditions=len(cases),
                timing_calls=len(calls), declared_loss_closure_checks=closure_checks,
                summary=expected_summary, auditor_sha256=digest(Path(__file__).read_bytes()),
                qualification='Saved metadata/timing reconciliation, not new model replay or external peer review.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
