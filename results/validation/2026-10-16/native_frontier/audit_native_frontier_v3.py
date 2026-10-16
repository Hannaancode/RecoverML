"""Audit complete paired native file-recovery evidence without loading models."""
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import tarfile

from recoverml.core import Graph, Node, digest
from recoverml.capability_retention import retained_bytes
from recoverml.dag_retention import verify_proof


def require(condition, message):
    if not condition:
        raise ValueError(message)


def members(path):
    with tarfile.open(path) as archive:
        items = [m for m in archive if m.isfile()]
        require(len(items) == len({m.name for m in items}), 'Duplicate archive member')
        return {m.name: archive.extractfile(m).read() for m in items}


def identities(records, expected):
    require(Counter((r['history'], r['method'], r['repetition']) for r in records) ==
            Counter({key: 1 for key in expected}), 'Missing, duplicate or unexpected native request')


def check_artifact(block_root, source_commit):
    receipt = json.loads((block_root / 'artifact_receipt.json').read_bytes())
    require(receipt['artifact']['workflow_run']['head_sha'] == source_commit, 'Artifact source commit differs')
    packed = {}
    for phase in ('native_paired', 'native_smoke'):
        for archive in ('captures.tar.gz', 'case_receipts.tar.gz'):
            for name, raw in members(block_root / phase / archive).items():
                key = phase + '/' + name
                require(key not in packed, 'Duplicate packed native evidence')
                packed[key] = raw
    expected_packed = {p for p in receipt['files'] if '/captures/' in p or '/cases/' in p}
    require(set(packed) == expected_packed, 'Packed native evidence inventory differs')
    for path, info in receipt['files'].items():
        require(not Path(path).is_absolute() and '..' not in Path(path).parts and ':' not in path and '\\' not in path,
                'Unsafe native artifact path')
        raw = packed[path] if path in packed else (block_root / path).read_bytes()
        require(digest(raw) == info['sha256'] and len(raw) == info['bytes'], 'Original native artifact member differs')
    return dict(artifact_id=receipt['artifact']['id'], zip_digest=receipt['artifact']['digest'],
                checked_members=len(receipt['files']))


def run(directory, source_commit, root):
    results = []
    totals = Counter()
    files = {}
    artifacts = []
    for seed in (20261016, 20261017, 20261018):
        block = directory / ('seed' + str(seed)) / 'native_paired'
        artifacts.append(check_artifact(block.parent, source_commit))
        end = json.loads((block / 'run_end.json').read_bytes())
        start = json.loads((block / 'run_start.json').read_bytes())
        protocol = json.loads((block / 'protocol.json').read_bytes())
        require(start['commit'] == source_commit and end['status'] == 'PASS' and not end['source_changed'],
                'Native block failed or source differs')
        require(protocol['datasets'] == ['wine', 'breast_cancer'] and protocol['versions'] == [4, 16, 64]
                and protocol['concat_materialized'] == [False, True] and protocol['repetitions'] == 3
                and protocol['seeds'] == [20261016, 20261017, 20261018]
                and protocol['methods'] == ['RecoverML_native', 'DVC_native_batch'], 'Native grid changed')
        for path, expected in end['closed_evidence_sha256'].items():
            require(digest((block / path).read_bytes()) == expected, 'Closed native evidence differs: ' + path)
        archived_source = members(block / 'source_snapshot.tar.gz')
        require(set(archived_source) == set(start['source_sha256']), 'Native source inventory differs')
        for path, expected in start['source_sha256'].items():
            raw = archived_source[path]
            require(digest(raw) == expected, 'Native source hash differs')
            committed = subprocess.check_output(['git', '-C', str(root), 'show', source_commit + ':' + path])
            require(raw == committed, 'Native source differs from pinned commit')
        captured = members(block / 'captures.tar.gz')
        cases = members(block / 'case_receipts.tar.gz')
        histories = {f'{data}-s{seed}-v{versions}-concat{int(concat)}'
                     for data, versions, concat in itertools.product(protocol['datasets'], protocol['versions'], protocol['concat_materialized'])}
        records = [json.loads(line) for line in (block / 'raw_recovery.jsonl').read_text().splitlines() if line]
        expected = {(h, m, rep) for h, m, rep in itertools.product(histories, protocol['methods'], range(3))}
        identities(records, expected)
        commands = json.loads((block / 'commands.json').read_bytes())
        require(all(r['returncode'] == 0 for r in commands), 'Native command failed')
        command_index = {r['label']: r for r in commands}
        require(len(command_index) == len(commands), 'Duplicate command identity')
        for history in sorted(histories):
            manifest = json.loads(captured['captures/' + history + '/manifest.json'])
            require(manifest['schema'] == 1, 'Unsupported native graph schema')
            graph = Graph(env=manifest['environment'])
            graph.nodes = {n['id']: Node(**n) for n in manifest['nodes']}
            graph.targets = manifest['targets']
            graph.roots = set(manifest['mandatory_blobs'])
            caps = {n.id: 'shared_standardization_entrypoint' for n in graph.nodes.values() if n.op == 'view_standardize'}
            retention = json.loads(cases['cases/' + history + '/retention.json'])
            selected = set(retention['selected'])
            verify_proof(graph, caps, 1, selected, retention['proof'])
            targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
            require(set(retention['target_sha256']) == targets, 'Native protected targets differ')
            for blob in graph.candidates:
                require(digest(captured['captures/' + history + '/blobs/' + blob + '.pkl']) == blob,
                        'Native captured payload hash differs')
            relevant = [r for r in records if r['history'] == history]
            for record in relevant:
                require(set(record['initial_payloads']) == selected and record['no_downstream_cache_before'] is True,
                        'Native initial frontier/cache differs')
                if protocol.get('baseline_revision', 1) >= 3:
                    require(set(record['native_cache_sha256']) <= selected and
                            record['unique_initial_payload_bytes'] == sum(graph.sizes()[b] for b in selected),
                            'Native paid-cache or unique physical byte accounting differs')
                require(record['exact_targets'] == record['expected_targets'] == len(targets)
                        and record['target_sha256'] == {b: b for b in targets}, 'Native target verification differs')
                require(record['common_bytes'] == retention['common_bytes'] == retained_bytes(graph, selected, caps, 1),
                        'Native common-byte accounting differs')
                require(all(math.isfinite(record[k]) and record[k] >= 0 for k in ('elapsed_s', 'subprocess_s', 'child_cpu_s'))
                        and record['elapsed_s'] >= record['subprocess_s'], 'Invalid native timing')
                command = command_index[history + ':' + record['method'] + ':' + str(record['repetition'])]
                require(command['elapsed_s'] == record['subprocess_s'] and command['cpu_s'] == record['child_cpu_s'],
                        'Native timing/command link differs')
                worker_name = 'cases/' + history + '/' + record['method'] + '_' + str(record['repetition']) + '.json'
                if record['core_s'] is not None:
                    worker = json.loads(cases[worker_name])
                    require(worker['status'] == 'PASS' and worker['core_elapsed_s'] == record['core_s']
                            and worker['target_sha256'] == {b: b for b in targets}, 'Native worker receipt differs')
                    for operation in worker['operations']:
                        require(operation.get('op') != 'view_standardize' and
                                (operation.get('producer') is None or operation['producer'] not in caps),
                                'A retired view was dispatched')
            for repetition in range(3):
                pair = [r for r in relevant if r['repetition'] == repetition]
                require({r['paired_order'] for r in pair} == {0, 1}, 'Native paired order differs')
            medians = {m: statistics.median(r['elapsed_s'] for r in relevant if r['method'] == m)
                       for m in protocol['methods']}
            ratio = medians['DVC_native_batch'] / medians['RecoverML_native']
            comparison = next(r for r in end['comparisons'] if r['history'] == history)
            require(comparison['median_s'] == medians and comparison['dvc_to_recoverml_ratio'] == ratio,
                    'Native comparison differs from raw records')
            results.append(dict(history=history, seed=seed, common_bytes=retention['common_bytes'],
                                downstream_targets=len(targets - selected), median_s=medians,
                                dvc_to_recoverml_ratio=ratio))
        require((end['histories'], end['native_commands'], end['exact_target_checks']) ==
                (12, 72, sum(r['exact_targets'] for r in records)), 'Native end totals differ')
        totals.update(native_commands=len(records), exact_target_checks=sum(r['exact_targets'] for r in records))
        for path in block.iterdir():
            if path.is_file():
                files[path.relative_to(directory).as_posix()] = digest(path.read_bytes())
        print(json.dumps(dict(verified_seed=seed, status='PASS')), flush=True)
    summary = {}
    for label, selected in [('all', results), ('recomputation_required', [r for r in results if r['downstream_targets']]),
                            ('all_targets_retained', [r for r in results if not r['downstream_targets']])]:
        summary[label] = dict(histories=len(selected), RecoverML_faster=sum(r['dvc_to_recoverml_ratio'] > 1 for r in selected),
            DVC_faster=sum(r['dvc_to_recoverml_ratio'] < 1 for r in selected),
            median_dvc_to_recoverml_ratio=statistics.median(r['dvc_to_recoverml_ratio'] for r in selected),
            minimum_dvc_to_recoverml_ratio=min(r['dvc_to_recoverml_ratio'] for r in selected),
            maximum_dvc_to_recoverml_ratio=max(r['dvc_to_recoverml_ratio'] for r in selected))
    return dict(schema=1, status='PASS', source_commit=source_commit,
        auditor_sha256=digest(Path(__file__).read_bytes()), artifacts=artifacts, totals=dict(totals), summary=summary,
        comparisons=results, checked_input_sha256=files,
        qualification='Descriptive whole-history subprocess latency for these authored integrations and hosts. '
        'Includes cold CLI bootstrap; core times are separately retained. No storage win over the optimal frontier, '
        'no global DVC inferiority claim, no independent-workload significance or external human review.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refuse to overwrite an audit')
    report = run(args.directory, args.source_commit, Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(report['summary'], indent=2))
