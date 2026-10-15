#!/usr/bin/env python3
"""Recheck archived paper byte accounting and exact storage optima.

Archives are read as data without extracting paths or unpickling payloads.
The current two independent formulations re-solve captured graph metadata;
this is not a claim of replay in a second environment. All discovered cases
and solver-unknown outcomes remain in the report.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

from recoverml.core import Graph, Node
from recoverml.capability_retention import contract, retained_bytes, restricted
from recoverml.component_retention import optimize as decomposed
from recoverml.scenario_retention import optimize as expanded
from recoverml.witness import certificate


DEFAULT_SUITES = ('protocol_pilot', 'tabular', 'estimators', 'published',
                  'merged', 'components', 'fault_scope')
SAFE_POLICIES = ('RecoverML_decomposed', 'robust', 'decomposed', 'expanded_exact', '')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_graph(manifest):
    if manifest['schema'] != 1:
        raise ValueError('Unsupported manifest schema')
    graph = Graph(env=manifest['environment'])
    graph.nodes = {n['id']: Node(**n) for n in manifest['nodes']}
    graph.targets = manifest['targets']
    graph.roots = set(manifest['mandatory_blobs'])
    return graph


def read_stores(archive):
    stores = {}
    entries = {}
    with tarfile.open(archive, 'r|gz') as stream:
        for member in stream:
            if member.isdir():
                continue
            if not (member.isfile() or member.islnk()):
                raise ValueError('Unsupported archive member type: ' + member.name)
            parts = PurePosixPath(member.name).parts
            if '..' in parts or member.name.startswith('/'):
                raise ValueError('Unsafe archived path: ' + member.name)
            parts = parts[1:] if parts and parts[0] == 'stores' else parts
            if len(parts) < 2:
                raise ValueError('Unknown archive member: ' + member.name)
            is_blob = len(parts) >= 3 and parts[-2] == 'blobs'
            key = '/'.join(parts[:-2] if is_blob else parts[:-1])
            record = stores.setdefault(key, dict(files=0, actual_bytes=0, payload_bytes=0,
                                                 hardlink_files=0, retained=[], errors=[]))
            if member.islnk():
                # tar hardlinks preserve earlier files without another payload.
                # Each independently measured policy store counts logical file
                # lengths, as pathlib.stat does in the original experiment.
                if member.linkname not in entries:
                    raise ValueError('Missing or forward hardlink: ' + member.name)
                entry = entries[member.linkname]
                record['hardlink_files'] += 1
            else:
                raw = stream.extractfile(member).read()
                entry = dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                if parts[-1] in ('manifest.json', 'capability_contract.json'):
                    entry['json'] = json.loads(raw)
            entries[member.name] = entry
            record['files'] += 1
            record['actual_bytes'] += entry['size']
            if is_blob:
                expected = parts[-1].removesuffix('.pkl')
                actual = entry['sha256']
                if actual != expected:
                    record['errors'].append('Payload hash mismatch: ' + parts[-1])
                record['retained'].append(expected)
                record['payload_bytes'] += entry['size']
            elif parts[-1] == 'manifest.json':
                record['manifest'] = entry['json']
                record['manifest_bytes'] = entry['size']
            elif parts[-1] == 'capability_contract.json':
                record['contract'] = entry['json']
                record['contract_bytes'] = entry['size']
            else:
                record['errors'].append('Unaccounted archived file: ' + member.name)
    return stores


def audit_suite(folder, time_limit_s, maximum_direct_variables):
    archive = folder / 'stores.tar.gz'
    stores = read_stores(archive)
    summaries = {}
    summary_path = folder / 'summary.csv'
    if summary_path.exists():
        with summary_path.open(newline='') as stream:
            summaries = {(r['case'], r['policy']): r for r in csv.DictReader(stream)
                         if 'case' in r and 'retained_bytes' in r}
    cases = {}
    store_rows = []
    for key, store in sorted(stores.items()):
        if 'manifest' not in store or 'contract' not in store:
            raise ValueError('Incomplete store metadata: ' + key)
        graph = load_graph(store['manifest'])
        caps = store['contract']['capabilities']
        k = store['contract']['maximum_lost_groups']
        selected = set(store['retained'])
        errors = store['errors']
        if not selected <= graph.candidates:
            errors.append('Retained payload absent from manifest')
        expected = retained_bytes(graph, selected, caps, k)
        if expected != store['actual_bytes']:
            errors.append('Actual byte total differs from objective')
        if graph.metadata_bytes() != store['manifest_bytes']:
            errors.append('Manifest bytes differ from canonical objective')
        if len(contract(caps, k)) != store['contract_bytes']:
            errors.append('Capability metadata differs from canonical objective')
        if not graph.roots <= selected:
            errors.append('Mandatory root not retained')
        # Components use one selected store per graph; other suites use a
        # case/policy pair. Do not infer independent histories from policies.
        case, separator, policy = key.rpartition('/')
        if not separator:
            case, policy = key, ''
        old = summaries.get((case, policy))
        if old and int(old['retained_bytes']) != store['actual_bytes']:
            errors.append('Published CSV byte total differs from actual store')
        row = dict(store=key, case=case, policy=policy, actual_bytes=store['actual_bytes'],
                   payload_bytes=store['payload_bytes'], manifest_bytes=store['manifest_bytes'],
                   contract_bytes=store['contract_bytes'], payload_files=len(selected),
                   archive_hardlink_files=store['hardlink_files'],
                   csv_accounting_checked=old is not None, errors=errors)
        store_rows.append(row)
        if policy in SAFE_POLICIES:
            rank = SAFE_POLICIES.index(policy)
            if case not in cases or rank < cases[case][0]:
                cases[case] = (rank, graph, caps, k, selected, row)
    case_rows = []
    for case, (_, graph, caps, k, selected, row) in sorted(cases.items()):
        groups = sorted(set(caps.values()))
        scenarios = sum(math.comb(len(groups), i) for i in range(min(k, len(groups)) + 1))
        availability_checked = scenarios <= 2000
        robust = (all(certificate(restricted(graph, caps, f), selected)['complete']
                      for count in range(min(k, len(groups)) + 1)
                      for f in itertools.combinations(groups, count))
                  if availability_checked else None)
        active_producers = sum(n.replayable for n in graph.nodes.values())
        estimated_direct_variables = len(graph.candidates) + scenarios * (
            2 * len(graph.candidates) + active_producers)
        results = {}
        for name, solver in (('decomposed', decomposed), ('expanded_exact', expanded)):
            if name == 'expanded_exact' and estimated_direct_variables > maximum_direct_variables:
                results[name] = dict(status='resource_guard', storage_optimal=False,
                                     robust_certified=False, reason='predeclared variable limit',
                                     estimated_variables=estimated_direct_variables)
                continue
            start = time.perf_counter()
            try:
                retained, status, diagnostic = solver(graph, caps, k, time_limit_s=time_limit_s)
                results[name] = dict(status=status, elapsed_s=time.perf_counter()-start,
                                     retained_bytes=retained_bytes(graph, retained, caps, k),
                                     diagnostic=diagnostic,
                                     storage_optimal=bool(diagnostic.get('storage_optimal')),
                                     robust_certified=bool(diagnostic.get('robust_certified')))
            except Exception as exc:
                results[name] = dict(status='error', elapsed_s=time.perf_counter()-start,
                                     storage_optimal=False, robust_certified=False,
                                     error_type=type(exc).__name__, error=str(exc))
        certified = [r for r in results.values() if r['status'] == 'ok' and
                     r['storage_optimal'] and r['robust_certified']]
        disagreement = any(r['retained_bytes'] != row['actual_bytes'] for r in certified)
        case_rows.append(dict(case=case, archived_store=row['store'], archived_bytes=row['actual_bytes'],
                              groups=len(groups), k=k, scenarios=scenarios,
                              selected_store_robust=robust, all_scenarios_checked=availability_checked,
                              estimated_direct_variables=estimated_direct_variables,
                              independent_formulations_certified=len(certified) == 2,
                              any_certified_disagreement=disagreement, solvers=results))
        print(json.dumps(dict(suite=folder.name, case=case,
                              both_certified=len(certified) == 2,
                              disagreement=disagreement)), flush=True)
    return dict(suite=folder.name, archive_sha256=sha256(archive),
                stores=len(store_rows), cases=len(case_rows),
                accounting_errors=sum(bool(r['errors']) for r in store_rows),
                csv_accounting_checks=sum(r['csv_accounting_checked'] for r in store_rows),
                all_stored_payload_hashes_checked=True,
                solver_unknown_cases=sum(not r['independent_formulations_certified'] for r in case_rows),
                disagreements=sum(r['any_certified_disagreement'] for r in case_rows),
                stored_safe_policy_failures=sum(r['selected_store_robust'] is False for r in case_rows),
                store_results=store_rows, case_results=case_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('results/research/paper_oct14'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suites', nargs='+', choices=DEFAULT_SUITES, default=DEFAULT_SUITES)
    parser.add_argument('--time-limit-s', type=float, default=30.)
    parser.add_argument('--maximum-direct-variables', type=int, default=100000)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be new so earlier diagnostics remain preserved')
    if args.time_limit_s <= 0 or not math.isfinite(args.time_limit_s):
        parser.error('Positive finite per-solver time limit required')
    start = time.perf_counter()
    report = dict(schema=1, started_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  command=sys.argv, python=sys.version, platform=platform.platform(),
                  source_sha256=sha256(Path(__file__)), time_limit_s=args.time_limit_s,
                  maximum_direct_variables=args.maximum_direct_variables,
                  scope='Current metadata solvers and intact archived payload byte accounting; no unpickling, archived replay, second-machine reproduction or energy claim',
                  suites=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suite in args.suites:
        report['suites'].append(audit_suite(args.source / suite, args.time_limit_s,
                                            args.maximum_direct_variables))
        args.output.write_text(json.dumps(report, indent=2)+'\n')
    report['elapsed_s'] = time.perf_counter()-start
    report['summary'] = {key: sum(r[key] for r in report['suites']) for key in
                         ('stores', 'cases', 'accounting_errors', 'csv_accounting_checks',
                          'solver_unknown_cases', 'disagreements', 'stored_safe_policy_failures')}
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['summary'], indent=2))
    if any(report['summary'][key] for key in ('accounting_errors', 'disagreements', 'stored_safe_policy_failures')):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
