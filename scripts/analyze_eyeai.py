#!/usr/bin/env python3
"""Reconcile the complete declared retinal grid and report ties and tradeoffs."""
import argparse
import csv
import gzip
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

POLICIES = ('RecoverML_exact', 'robust_greedy', 'robust_local',
            'DVC_target_snapshots', 'DVC_all_stages')


def analyze(directory):
    directory = Path(directory)
    protocol = json.loads((directory / 'protocol.json').read_text())
    with (directory / 'summary.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    expected = set(itertools.product(protocol['estimators'], map(str, protocol['seeds']),
        map(str, protocol['versions']), protocol['targets'], protocol['availability'], POLICIES))
    fields = ('estimator', 'seed', 'versions', 'target_mode', 'availability', 'policy')
    keys = [tuple(row[field] for field in fields) for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise RuntimeError('Summary does not match the entire predeclared grid')
    path = directory / 'raw.jsonl.gz'
    opener = gzip.open if path.exists() else open
    if not path.exists():
        path = directory / 'raw.jsonl'
    counts, seen, raw_total, raw_exact, cdf = {}, set(), 0, 0, {}
    with opener(path, 'rt') as handle:
        for line in handle:
            record = json.loads(line)
            key = (record['condition_id'], tuple(record['fault']), record['version'])
            if key in seen:
                raise RuntimeError('Duplicate raw recovery request')
            seen.add(key)
            raw_total += 1
            exact = bool(record['exact']) and record['actual_sha256'] == record['expected_sha256']
            raw_exact += exact
            state = counts.setdefault(record['condition_id'], dict(requests=0, exact=0, errors=0))
            state['requests'] += 1
            state['exact'] += exact
            state['errors'] += record['error'] is not None
            if (record['estimator'] == 'forest' and record['versions'] == max(protocol['versions'])
                and record['target_mode'] == 'model_prediction' and record['availability'] == 'legacy_removed'):
                cdf.setdefault(record['policy'], []).append(record['elapsed_s'])
    if raw_total != protocol['expected_recovery_requests']:
        raise RuntimeError('Raw request total differs from fixed protocol')
    for row in rows:
        for field in ('requests', 'exact', 'errors'):
            if int(row[field]) != counts.get(row['condition_id'], {}).get(field):
                raise RuntimeError('Raw and summary disagree: ' + row['condition_id'] + ' ' + field)
    groups = {}
    for row in rows:
        groups.setdefault(tuple(row[field] for field in fields[:-1]), {})[row['policy']] = row
    comparisons = []
    for key, methods in groups.items():
        exact = methods['RecoverML_exact']
        snapshot = methods['DVC_target_snapshots']
        saved = int(snapshot['retained_bytes']) - int(exact['retained_bytes'])
        comparisons.append(dict(zip(fields[:-1], key), exact_bytes=int(exact['retained_bytes']),
            snapshot_bytes=int(snapshot['retained_bytes']), saved_bytes=saved,
            saved_fraction=saved / int(snapshot['retained_bytes']),
            greedy_excess_bytes=int(methods['robust_greedy']['retained_bytes']) - int(exact['retained_bytes']),
            local_excess_bytes=int(methods['robust_local']['retained_bytes']) - int(exact['retained_bytes']),
            exact_planning_s=float(exact['planning_s']),
            exact_mean_restore_s=float(exact['mean_restore_s']),
            snapshot_mean_restore_s=float(snapshot['mean_restore_s'])))
    commands = json.loads((directory / 'native_commands.json').read_text())
    native = [command for command in commands if command['command'][1:4] == ['-m', 'dvc', 'checkout']]
    analysis = dict(status='PASS', summary_rows=len(rows), raw_requests=raw_total,
        exact_requests=raw_exact, unexpected_errors=sum(int(row['errors']) for row in rows),
        exact_comparison_conditions=len(comparisons),
        native_checkout_commands=len(native), native_failed_commands=sum(c['returncode'] != 0 for c in commands),
        positive_savings_conditions=sum(c['saved_bytes'] > 0 for c in comparisons),
        zero_savings_conditions=sum(c['saved_bytes'] == 0 for c in comparisons),
        negative_savings_conditions=sum(c['saved_bytes'] < 0 for c in comparisons),
        exact_beats_greedy=sum(c['greedy_excess_bytes'] > 0 for c in comparisons),
        exact_ties_greedy=sum(c['greedy_excess_bytes'] == 0 for c in comparisons),
        exact_beats_local=sum(c['local_excess_bytes'] > 0 for c in comparisons),
        exact_ties_local=sum(c['local_excess_bytes'] == 0 for c in comparisons),
        maximum_saved_bytes=max(c['saved_bytes'] for c in comparisons),
        comparisons=comparisons,
        statistical_unit='Three seed blocks on the same 20 images, not 108 independent studies',
        timing_scope='One repetition per actual request, uncontrolled host cache and system load; descriptive only',
        native_timing_scope='Snapshot read/decoding timed each request; native DVC CLI checkout timed once per version and reused across availability/fault conditions')
    if raw_exact != raw_total or analysis['unexpected_errors']:
        analysis['status'] = 'FAIL'
    (directory / 'analysis.json').write_text(json.dumps(analysis, indent=2) + '\n')
    economic_rows = []
    for key, methods in groups.items():
        ours, baseline = methods['RecoverML_exact'], methods['DVC_target_snapshots']
        saved_gib = (int(baseline['retained_bytes']) - int(ours['retained_bytes'])) / 2**30
        ours_cpu_per_request = float(ours['recovery_cpu_s']) / int(ours['requests'])
        baseline_cpu_per_request = float(baseline['recovery_cpu_s']) / int(baseline['requests'])
        for requests, days in itertools.product((1, 10, 100), (1, 30, 365)):
            additional_cpu = float(ours['planning_cpu_s']) + requests * (ours_cpu_per_request - baseline_cpu_per_request)
            gib_days = saved_gib * days
            economic_rows.append(dict(zip(fields[:-1], key), restores=requests, retention_days=days,
                saved_gib_days=gib_days, additional_cpu_s=additional_cpu,
                break_even_cpu_seconds_per_gib_day=additional_cpu / gib_days if gib_days > 0 else '',
                qualification='Measured process CPU and common bytes; no energy, transfer, SLA or cloud price claim'))
    with (directory / 'economics.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(economic_rows[0]))
        writer.writeheader()
        writer.writerows(economic_rows)
    figure_dir = directory / 'plots'
    figure_dir.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for axis, availability in zip(axes, protocol['availability']):
        for policy in POLICIES:
            points = []
            for versions in protocol['versions']:
                values = [int(row['retained_bytes']) / 1e6 for row in rows if
                    row['estimator'] == 'forest' and row['target_mode'] == 'model_prediction'
                    and row['availability'] == availability and row['policy'] == policy
                    and int(row['versions']) == versions]
                points.append(np.mean(values))
            axis.plot(protocol['versions'], points, marker='o', label=policy)
        axis.set_title(availability.replace('_', ' '))
        axis.set_xlabel('Historical versions')
        axis.grid(alpha=.25)
    axes[0].set_ylabel('Retained common bytes (MB)')
    axes[-1].legend(fontsize=7)
    fig.suptitle('Constructed retinal forest histories — means of three fixed seed blocks')
    fig.tight_layout()
    fig.savefig(figure_dir / 'retained_storage.png', dpi=180)
    plt.close(fig)
    if cdf:
        fig, axis = plt.subplots(figsize=(7, 4))
        for policy, values in cdf.items():
            values = np.sort(values)
            axis.step(values, np.arange(1, len(values) + 1) / len(values), where='post', label=policy)
        axis.set_xscale('log')
        axis.set_xlabel('Actual disk recovery seconds (log scale)')
        axis.set_ylabel('Fraction of requests')
        axis.set_title('Forest model and prediction targets — legacy retirement\nLargest fixed history, three seed blocks, DVC CLI cost separate')
        axis.legend(fontsize=8)
        axis.grid(alpha=.25)
        fig.tight_layout()
        fig.savefig(figure_dir / 'recovery_latency_cdf.png', dpi=180)
        plt.close(fig)
    maximum = max(comparisons, key=lambda item: item['saved_bytes'])
    text = ['# Verified rebuilt EyeAI-inspired retinal study', '',
        'These are newly executed constructed histories on all 20 STARE images and their Adam Hoover vessel annotations. They are inspired by the published EyeAI processing-revision example and are not a clinical reproduction of EyeAI.', '',
        f"Grid reconciliation: **{analysis['status']}** with {len(rows)} method rows and {raw_total} actual disk recovery requests and {raw_exact} exact recoveries and {analysis['unexpected_errors']} unexpected errors.", '',
        f"Native DVC: {len(native)} actual checkout commands. Each output hash was verified. Their receipts are reused across matching availability conditions and are not counted as new native executions.", '',
        '| Comparison against the certified exact minimum | Conditions |', '|---|---:|',
        f"| Exact saves bytes against target snapshots | {analysis['positive_savings_conditions']} |",
        f"| Exact ties target snapshots | {analysis['zero_savings_conditions']} |",
        f"| Exact beats simple robust greedy | {analysis['exact_beats_greedy']} |",
        f"| Exact ties simple robust greedy | {analysis['exact_ties_greedy']} |",
        f"| Exact beats strong local heuristic | {analysis['exact_beats_local']} |",
        f"| Exact ties strong local heuristic | {analysis['exact_ties_local']} |", '',
        f"Largest absolute target-snapshot saving: **{maximum['saved_bytes']:,} bytes** ({maximum['saved_fraction']:.2%}) for {maximum['estimator']} seed {maximum['seed']} with {maximum['versions']} versions and targets {maximum['target_mode']} under {maximum['availability']}.", '',
        'Savings come from preserving common inputs or an earlier feature frontier and replaying model stages. Snapshot loads can be much faster than retraining. Broad retirement of both training and prediction forces target retention and can remove all target-snapshot savings. A heuristic matching the exact minimum is a tie and is not evidence of an optimization advantage.', '',
        'The practical question has two parts. These histories show whether selective retention can save storage and whether the particular exact solver improves the decision over the tested strong heuristic. Large artifact count and a large percentage saving do not by themselves establish hard or meaningful optimization choices. The heuristic gap counts above provide the direct test.', '',
        'The CSV contains planning wall time and process CPU time and P50/P90/P99 recovery latency. Raw JSONL records timestamps and CPU and process I/O counters and operation events and expected and actual SHA-256 hashes. `economics.csv` gives measured CPU-seconds per saved GiB-day break-even ratios for 1/10/100 restores and 1/30/365 retention days. No cloud price is invented.', '',
        'Timing uses one request repetition on this host with no cold-cache isolation. The three seeds reuse the same 20 images and version counts are nested design settings. These are descriptive results rather than evidence from 108 independent production workflows. Native DVC checkout cost is separate from direct snapshot reads and includes CLI startup. Full native DVC replay is a separate control.', '']
    (directory / 'RESULTS.md').write_text('\n'.join(text))
    print(json.dumps({key: value for key, value in analysis.items() if key != 'comparisons'}, indent=2))
    return analysis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    analyze(parser.parse_args().directory)
