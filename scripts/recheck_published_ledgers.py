"""Recheck available ledgers on disposable copies; never rewrite original evidence.

This does not replay fitted models, verify absent frontier payloads, or substitute
for the original scientific analyzer that requires unpublished capture archives.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def storage_plot(folder, destination):
    import matplotlib.pyplot as plt
    plans = json.loads((folder / 'planner_records.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for axis, scope in zip(axes, ('preprocessing', 'broad')):
        selected = [p for p in plans if p['scope'] == scope]
        values = [p['retained_bytes'] / 1e9 for p in selected]
        axis.bar(range(len(selected)), values, color=['#16758c', '#748ba3', '#bf8957', '#859d52', '#666666'])
        for index, (value, row) in enumerate(zip(values, selected)):
            label = f'{value:.3f} GB' if value >= 1 else f'{value * 1000:.2f} MB'
            complete = row['allowed_structural_exact'] == row['allowed_structural_requests']
            if not complete:
                label += f"\npartial {row['allowed_structural_exact']}/{row['allowed_structural_requests']}"
            axis.text(index, value + .045, label, ha='center', va='bottom', fontsize=8,
                      color='black' if complete else '#a12424')
        axis.set_xticks(range(len(selected)), [p['policy'].replace('_', '\n') for p in selected], fontsize=8)
        axis.set_ylim(0, 4.15)
        axis.set_title(scope + ' capability loss; k=1')
        axis.set_ylabel('Retained canonical storage (decimal GB)')
        axis.grid(axis='y', alpha=.2)
        axis.set_axisbelow(True)
    fig.suptitle('UCI Letter history — partial recovery is labelled; heuristics can tie exact storage')
    fig.tight_layout()
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    large = ROOT / 'results/research/gigabyte_letter_oct16'
    retinal = ROOT / 'results/research/eyeai_complete_oct15'
    before = dict(large=hashes(large), retinal=hashes(retinal))
    analyze_large = module('large_analyzer', 'analyze_gigabyte_history.py')
    control = module('large_controls', 'audit_gigabyte_ledger.py')
    analyze_retinal = module('retinal_analyzer', 'analyze_eyeai.py')
    with tempfile.TemporaryDirectory(prefix='recoverml_ledger_recheck_') as temporary:
        scratch = Path(temporary)
        large_copy = scratch / 'large'
        retinal_copy = scratch / 'retinal'
        shutil.copytree(large, large_copy)
        shutil.copytree(retinal, retinal_copy)
        checked_large = analyze_large.analyze(large_copy)
        checked_retinal = analyze_retinal.analyze(retinal_copy)
        numeric = control.cross_links(large_copy)
        dump(output / 'large_metadata.json', checked_large)
        dump(output / 'retinal_reconciliation.json', checked_retinal)
        dump(output / 'large_numeric_cross_links.json', numeric)
        # Repeat the six semantic controls on ledger copies. The original
        # archive-verification control still requires selected_frontier.tar.gz.
        # Its absence is reported, not suppressed in that original command.
        analyze_large.write_results = lambda *unused: None
        cases = []
        names = ('unchanged', 'structural_reordered', 'structural_duplicate_identity',
                 'structural_flipped_recoverability', 'structural_missing_record', 'runtime_duplicate_identity')
        for name in names:
            folder = scratch / name
            folder.mkdir()
            for item in control.INPUTS:
                if (large / item).is_file():
                    shutil.copy2(large / item, folder / item)
            path = folder / 'allowed_scenario_certificates.json'
            records = json.loads(path.read_text())
            if name == 'structural_reordered':
                records.reverse()
            elif name == 'structural_duplicate_identity':
                records[1] = dict(records[0])
            elif name == 'structural_flipped_recoverability':
                records[0]['recoverable'] = not records[0]['recoverable']
            elif name == 'structural_missing_record':
                records.pop()
            if name.startswith('structural_'):
                dump(path, records)
            if name == 'runtime_duplicate_identity':
                path = folder / 'execution_traces.jsonl.gz'
                with gzip.open(path, 'rt') as stream:
                    records = [json.loads(line) for line in stream]
                records[1] = dict(records[0])
                with gzip.open(path, 'wt') as stream:
                    for row in records:
                        stream.write(json.dumps(row) + '\n')
            answer = analyze_large.analyze(folder)
            expected = 'PASS' if name in ('unchanged', 'structural_reordered') else 'FAIL'
            cases.append(dict(case=name, expected=expected, actual=answer['status'],
                              passed=answer['status'] == expected, errors=answer['errors']))
        dump(output / 'six_ledger_controls.json', cases)
        storage_plot(large_copy, output / 'large_storage_recomputed.png')
        shutil.copytree(retinal_copy / 'plots', output / 'retinal_plots')
    after = dict(large=hashes(large), retinal=hashes(retinal))
    result = dict(status='PASS' if checked_large['status'] == checked_retinal['status'] == numeric['status'] == 'PASS'
                  and all(c['passed'] for c in cases) and before == after else 'FAIL',
                  original_inputs_unchanged=before == after, semantic_controls_passed=sum(c['passed'] for c in cases),
                  large_payloads_replayed=False, missing_frontier_archive=not (large / 'selected_frontier.tar.gz').is_file(),
                  source_host=sys.platform, python=sys.version.split()[0],
                  scope='Ledger and structural reconciliation and six mutation controls on temporary copies. No new benchmark timings, DVC execution, or model payload verification.',
                  figures='New renders from existing measurements; not byte-identical recovery of missing historical figures.')
    dump(output / 'report.json', result)
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
