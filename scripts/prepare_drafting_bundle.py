"""Build the paper's frozen evidence tables using only the standard library.

This reads recorded evidence, not model payloads, and performs no experiment.
Use --check to compare the generated files without changing them. The source
commit is deliberately fixed: concurrent research pushes must be reviewed
before changing the paper's evidence cutoff.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e0c745a754599e45562067197da76ea7de0dd0e5'
CLOUD = 'results/research/strong_baseline_cloud_oct16'
DEST = ROOT / 'docs/drafting_oct17'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(source_commit):
    inputs = {}

    def read(path):
        data = subprocess.check_output(['git', '-C', str(ROOT), 'show', source_commit + ':' + path])
        inputs[path] = digest(data)
        return data

    def load(path):
        return json.loads(read(path))

    cloud = load(CLOUD + '/complete_audit.json')
    if cloud['status'] != 'PASS':
        raise ValueError('The cloud aggregate audit is not PASS')
    # Also bind every raw input checked by the independent cloud audit.
    for relative, expected in cloud['checked_input_sha256'].items():
        if digest(read(CLOUD + '/' + relative)) != expected:
            raise ValueError('Cloud audited input differs: ' + relative)

    scientific = load('results/research/scientific_complete_oct16/report.json')
    retinal = load('results/research/eyeai_complete_oct15/analysis.json')
    large = load('results/research/gigabyte_letter_oct16/analysis.json')
    timing = load(CLOUD + '/seed20261016/dag_timing/report.json')
    if retinal['status'] != large['status'] or large['status'] != timing['status'] or timing['status'] != 'PASS':
        raise ValueError('A supporting report is not PASS')

    cases, method_rows, method_summary = [], [], []
    for phase, report in cloud['phases'].items():
        for case in report['comparisons']:
            cases.append(dict(phase=phase, **case))
        phase_rows = []
        for seed in cloud['seeds']:
            raw = read(f'{CLOUD}/seed{seed}/{phase}/summary.csv').decode('utf-8')
            phase_rows.extend(csv.DictReader(io.StringIO(raw)))
        if len(phase_rows) != 324:
            raise ValueError('Incomplete cloud method grid')
        method_rows.extend(dict(phase=phase, **r) for r in phase_rows)
        for method in sorted({r['method'] for r in phase_rows}):
            subset = [r for r in phase_rows if r['method'] == method]
            method_summary.append(dict(
                phase=phase, method=method, conditions=len(subset),
                fully_recoverable_conditions=sum(r['fully_recoverable'] == 'True' for r in subset),
                method_attributed_requests=sum(int(r['requests']) for r in subset),
                method_attributed_exact=sum(int(r['exact']) for r in subset),
                method_attributed_expected_blocked=sum(int(r['expected_blocked']) for r in subset),
                unexpected=sum(int(r['unexpected']) for r in subset),
                budget=('exact_minimum' if method.startswith(('HYPPO', 'HELIX')) else 'full_candidate'),
                warning='Method outcomes share physical store executions; do not sum as unique requests'))
    if len(cases) != 72 or len({(r['phase'], r['history']) for r in cases}) != 72:
        raise ValueError('Incomplete or duplicated paired history/contract grid')
    if any(r['our_bytes'] > r['local_bytes'] or r['our_bytes'] != r['manual_bytes'] for r in cases):
        raise ValueError('Published storage comparison no longer matches the frozen claim')
    timings = []
    for r in timing['results']:
        timings.append(dict(case=r['case'], dag_eligible=r['dag_eligible'],
                            minimum_bytes=r['original_minimum'],
                            **{m + '_median_s': v for m, v in r['median_s'].items()},
                            speedup_vs_local=r['speedup_vs_local'],
                            speedup_vs_scenario=r['speedup_vs_scenario']))
    if len(timings) != 48:
        raise ValueError('Missing old-condition timing case')

    runtime = {key: sum(p['runtime'][key] for p in cloud['phases'].values())
               for key in ('requests', 'exact', 'expected_blocked', 'unexpected')}
    if runtime != dict(requests=19652, exact=16110, expected_blocked=3542, unexpected=0):
        raise ValueError('Frozen cloud actual-runtime counts changed')
    summary = dict(
        source_commit=source_commit, experiment_source_commit=cloud['source_commit'],
        cloud=dict(captured_histories=36, paired_contract_cases=len(cases),
                   method_rows=len(method_rows), actual_unique_requests=runtime,
                   phases={name: p['summary'] for name, p in cloud['phases'].items()}),
        scientific={k: scientific[k] for k in ('histories', 'requests', 'exact', 'expected_blocked', 'unexpected', 'source_guard_scope')},
        retinal={k: retinal[k] for k in ('raw_requests', 'exact_requests', 'exact_comparison_conditions', 'exact_beats_greedy', 'exact_ties_greedy', 'exact_beats_local', 'exact_ties_local', 'maximum_saved_bytes')},
        letter={k: large[k] for k in ('models', 'actual_runtime_requests', 'actual_exact', 'scopes', 'uncompressed_1GB_goal_met', 'gzip_1GB_goal_met')},
        old_condition_timing=cloud['old_condition_timing']['summary'],
        native_dvc_batch_v2='PENDING at frozen cutoff; do not infer a latency winner',
        scope='Frozen report extraction and byte verification, not a fresh execution or external novelty review')
    # Bind the manuscript bytes that preparation intentionally leaves unchanged.
    for path in ('paper/RecoverML_capability_loss.md', 'paper/RecoverML_draft.md',
                 'docs/NATIVE_FRONTIER_PROTOCOL_OCT16.md', 'configs/native_frontier_latency_oct16.json',
                 'docs/CONTRIBUTION_POSITIONING_OCT16.md'):
        read(path)

    def csv_text(rows):
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()

    outputs = {
        'results_summary.json': json.dumps(summary, indent=2) + '\n',
        'cloud_storage_cases.csv': csv_text(cases),
        'cloud_methods.csv': csv_text(method_rows),
        'cloud_method_summary.csv': csv_text(method_summary),
        'planner_timing_cases.csv': csv_text(timings),
    }
    manifest = dict(schema=1, source_commit=source_commit,
                    experiment_source_commit=cloud['source_commit'],
                    source_sha256=dict(sorted(inputs.items())),
                    generated_sha256={name: digest(data.encode('utf-8')) for name, data in outputs.items()},
                    formulas=dict(storage_percent='100 * (local_bytes - our_bytes) / local_bytes',
                                  planning_speedup='paired baseline median planning seconds / RecoverML median planning seconds',
                                  decimal_GB='bytes / 1000000000', decimal_MB='bytes / 1000000'),
                    cautions=['36 histories assessed under two contracts are 72 paired cases, not 72 independent histories',
                              'Method-attributed executions may share physical stores',
                              'Planning ratios are not recovery speedups',
                              'Missing original Letter frontier container remains disclosed',
                              'Pending native DVC batch v2 is excluded'])
    outputs['evidence_manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', default=BASE)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    outputs = build(args.source_commit)
    if args.check:
        different = [name for name, value in outputs.items()
                     if not (DEST / name).exists() or (DEST / name).read_bytes() != value.encode('utf-8')]
        if different:
            raise SystemExit('Generated drafting files differ: ' + ', '.join(different))
    else:
        DEST.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            (DEST / name).write_bytes(value.encode('utf-8'))
    print(json.dumps(dict(status='PASS', files=len(outputs), source_commit=args.source_commit,
                          operation='check' if args.check else 'generate')))


if __name__ == '__main__':
    main()
