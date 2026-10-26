"""Paired planner follow-up on every frozen condition and fixed scaling controls.

No model payload is opened. The reference modules are exact Git source bytes;
unchanged dependencies are shared to avoid timing separate interpreter startup.
"""
import argparse
from collections import Counter
import csv
import gzip
import io
import itertools
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tarfile
import time
import types

from threadpoolctl import threadpool_limits
from recoverml.core import Graph, Node, canonical, digest, environment
from recoverml.capability_retention import retained_bytes, restricted
from recoverml.component_retention import optimize as indexed
from recoverml.scenario_retention import optimize as scenario
from recoverml.robust_heuristics import fault_sets, select
from recoverml.witness import certificate

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['src/recoverml/component_retention.py', 'src/recoverml/dag_retention.py',
           'src/recoverml/robust_retention.py', 'src/recoverml/core.py',
           'src/recoverml/capability_retention.py', 'src/recoverml/witness.py',
           'src/recoverml/scenario_retention.py', 'src/recoverml/robust_heuristics.py',
           'scripts/benchmark_planner_efficiency.py', 'configs/planner_efficiency_oct26.json']


def reference(commit):
    import importlib
    package = '_recoverml_planner_reference'
    holder = types.ModuleType(package)
    holder.__path__ = []
    sys.modules[package] = holder
    for name in ('core', 'capability_retention', 'witness', 'scenario_retention'):
        path = 'src/recoverml/' + name + '.py'
        old = subprocess.check_output(['git', '-C', str(ROOT), 'show', commit + ':' + path])
        current = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:' + path])
        working = (ROOT / path).read_bytes().replace(b'\r\n', b'\n')
        if old != current or old.replace(b'\r\n', b'\n') != working:
            raise ValueError('Reference dependency changed: ' + path)
        sys.modules[package + '.' + name] = importlib.import_module('recoverml.' + name)
    hashes = {}
    for name in ('dag_retention', 'robust_retention', 'component_retention'):
        path = 'src/recoverml/' + name + '.py'
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', commit + ':' + path])
        hashes[path] = digest(raw)
        module = types.ModuleType(package + '.' + name)
        module.__package__ = package
        sys.modules[module.__name__] = module
        exec(compile(raw, 'git:' + commit + ':' + path, 'exec'), module.__dict__)
    return sys.modules[package + '.component_retention'].optimize, hashes


def read_graph(raw):
    m = json.loads(raw)
    g = Graph(env=m['environment'])
    g.nodes = {n['id']: Node(**n) for n in m['nodes']}
    g.targets, g.roots = m['targets'], set(m['mandatory_blobs'])
    return g


def csv_rows(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8'))))


def manifests(path):
    with tarfile.open(path) as archive:
        return {Path(m.name).parent.name: archive.extractfile(m).read()
                for m in archive if m.isfile() and m.name.endswith('/manifest.json')}


def frozen(group, inputs):
    from recoverml.scientific_workflows import caps_for
    from recoverml.eyeai_workflow import capabilities_for, target_view

    def checked(path):
        inputs[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
        return path

    if group == 'scientific':
        base = ROOT / 'results/research/scientific_complete_oct16'
        records = json.loads(gzip.decompress(checked(base / 'planner_records.json.gz').read_bytes()))
        expected = {r['case']: r['actual_bytes'] for r in records
                    if r['policy'] == 'RecoverML_exact' and 'budget_fraction' not in r}
        for history, raw in sorted(manifests(checked(base / 'captures.tar.gz')).items()):
            g = read_graph(raw)
            for scope, k in itertools.product(('preprocessing', 'broad'), (0, 1, 2)):
                key = history + '-' + scope + '-k' + str(k)
                yield key, g, caps_for(g, scope), k, expected[key]
    elif group == 'cloud':
        base = ROOT / 'results/research/strong_baseline_cloud_oct16'
        for seed, phase in itertools.product((20261016, 20261017, 20261018), ('separate', 'shared')):
            directory = base / ('seed' + str(seed)) / phase
            rows = csv_rows(checked(directory / 'summary.csv'))
            expected = {r['history']: int(r['retained_bytes']) for r in rows if r['method'] == 'RecoverML_exact'}
            for history, raw in sorted(manifests(checked(directory / 'captures.tar.gz')).items()):
                g = read_graph(raw)
                caps = {n.id: ('shared_standardization_entrypoint' if phase == 'shared'
                              else 'preprocessing_view_' + str(i))
                        for i, n in enumerate(n for n in g.nodes.values() if n.op == 'view_standardize')}
                yield phase + '/' + history, g, caps, 1, expected[history]
    elif group == 'retinal':
        base = ROOT / 'results/research/eyeai_complete_oct15'
        rows = csv_rows(checked(base / 'summary.csv'))
        for row in rows:
            if row['policy'] != 'RecoverML_exact':
                continue
            path = checked(base / 'captures' / row['capture_id'] / 'manifest.json')
            g = target_view(read_graph(path.read_bytes()), row['target_mode'])
            caps, k = capabilities_for(g, row['availability'])
            yield row['condition_id'], g, caps, k, int(row['retained_bytes'])
    elif group == 'letter':
        base = ROOT / 'results/research/gigabyte_letter_oct16'
        g = read_graph(checked(base / 'manifest.json').read_bytes())
        for row in csv_rows(checked(base / 'summary.csv')):
            if row['policy'] == 'RecoverML_exact':
                yield row['scope'], g, caps_for(g, row['scope']), 1, int(row['retained_bytes'])
    else:
        raise ValueError('Unknown frozen group')


def stress(topology, width, seed):
    g = Graph(env={})
    rng = random.Random(seed)
    def add(label, deps, size, replayable, root=False):
        ident = digest(label.encode())
        g.nodes[ident] = Node(ident, 'metadata_fixture', deps, {}, replayable, 'scaling',
                              digest(('blob:' + label).encode()), size, 0., 0)
        if root:
            g.roots.add(g.nodes[ident].blob)
        return ident
    root = add('root', [], 19, False, True)
    leaves = [add('leaf' + str(i), [], rng.randint(5, 11), False) for i in range(width)]
    minimum = sum(g.nodes[n].size for n in leaves)
    if topology == 'wide_frontier':
        join = add('join', leaves, minimum + 123, True)
        g.targets = {'0': [join]}
    elif topology == 'independent_branches':
        targets = []
        for i, leaf in enumerate(leaves):
            targets += [add('a' + str(i), [leaf, root], 31, True),
                        add('b' + str(i), [leaf, root], 37, True)]
        # Many target entries exercise the indexed target projection too.
        g.targets = {str(i): targets[2*i:2*i+2] for i in range(width)}
    else:
        raise ValueError('Unknown stress topology')
    expected = retained_bytes(g, g.roots | {g.nodes[n].blob for n in leaves}, {}, 0)
    return g, {}, 0, expected


def run(group, output, protocol):
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads(protocol.read_bytes())
    previous, old_hashes = reference(config['reference_commit'])
    source = {p: digest((ROOT / p).read_bytes()) for p in SOURCES}
    start = dict(group=group, timestamp_ns=time.time_ns(), environment=environment(),
                 commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip(),
                 source_sha256=source, reference_source_sha256=old_hashes, protocol=config)
    (output / 'run_start.json').write_text(json.dumps(start, indent=2)+'\n')
    inputs = {}
    if group == 'scaling':
        cases = [(topology + '-w' + str(width) + '-s' + str(seed), *stress(topology, width, seed))
                 for topology, width, seed in itertools.product(config['scaling_topologies'],
                        config['scaling_widths'], config['scaling_seeds'])]
        methods = config['scaling_methods']
    else:
        cases = list(frozen(group, inputs))
        methods = config['methods']
    if len(cases) != config['groups'][group] or len({c[0] for c in cases}) != len(cases):
        raise ValueError('Incomplete or duplicate fixed grid')
    calls = []
    selections = {}
    rows = []
    functions = {'RecoverML_indexed': indexed, 'RecoverML_previous': previous, 'scenario_exact': scenario}
    # Warm the Python libraries and both exact-engine paths outside measurement.
    warm, caps, k, _ = stress('independent_branches', 2, 0)
    with threadpool_limits(limits=1):
        for fn in functions.values():
            fn(warm, caps, k)
        select(warm, caps, k, retained_bytes(warm, warm.candidates, caps, k), True)
        for case, g, caps, k, expected in cases:
            original = digest(canonical(g.manifest()))
            budget = retained_bytes(g, g.candidates, caps, k)
            medians = {m: [] for m in methods}
            sizes = {}
            for rep in range(config['repetitions']):
                order = list(methods)
                random.Random(group + '/' + case + '/' + str(rep)).shuffle(order)
                for position, method in enumerate(order):
                    started = time.perf_counter()
                    cpu = time.process_time()
                    if method == 'robust_local':
                        selected, diag = select(g, caps, k, budget, True)
                        status = 'heuristic'
                    else:
                        selected, status, diag = functions[method](g, caps, k, time_limit_s=120.)
                    elapsed, used_cpu = time.perf_counter()-started, time.process_time()-cpu
                    actual = retained_bytes(g, selected, caps, k)
                    if method != 'robust_local' and (status != 'ok' or not diag.get('storage_optimal') or actual != expected):
                        raise RuntimeError('Exact optimum differs: ' + case + '/' + method)
                    if not diag.get('robust_certified') or not g.roots <= selected <= g.candidates:
                        raise RuntimeError('Invalid selected store')
                    if not all(certificate(restricted(g, caps, loss), selected)['complete']
                               for loss in fault_sets(caps, k)):
                        raise RuntimeError('Independent declared-loss closure failed')
                    if original != digest(canonical(g.manifest())):
                        raise RuntimeError('Planner mutated the captured manifest')
                    identity = digest(canonical(sorted(selected)))
                    selections[identity] = sorted(selected)
                    calls.append(dict(case=case, method=method, repetition=rep, order=position,
                        elapsed_s=elapsed, cpu_s=used_cpu, retained_bytes=actual, selected_sha256=identity,
                        status=status, robust_certified=True, storage_optimal=diag.get('storage_optimal', False)))
                    medians[method].append(elapsed)
                    sizes[method] = actual
            row = dict(case=case, expected_bytes=expected, nodes=len(g.nodes),
                       versions=len(g.targets), sizes=sizes,
                       median_s={m: statistics.median(v) for m, v in medians.items()})
            row['paired_speedup'] = {m: row['median_s'][m]/row['median_s']['RecoverML_indexed']
                                    for m in methods if m != 'RecoverML_indexed'}
            rows.append(row)
            # Close a checkpoint after each whole condition, never replace raw measurements.
            (output / 'progress.json').write_text(json.dumps(dict(completed=len(rows), total=len(cases), last=case))+'\n')
            with gzip.open(output / 'calls.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(calls, stream, allow_nan=False)
            with gzip.open(output / 'selections.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(selections, stream, allow_nan=False)
            print(group, len(rows), '/', len(cases), case, row['paired_speedup'], flush=True)
    changed = [p for p, sha in source.items() if digest((ROOT / p).read_bytes()) != sha]
    summary = {}
    for method in methods:
        if method == 'RecoverML_indexed':
            continue
        ratios = [r['paired_speedup'][method] for r in rows]
        summary[method] = dict(cases=len(rows), indexed_faster=sum(v > 1 for v in ratios),
            indexed_slower=sum(v < 1 for v in ratios), median_paired_speedup=statistics.median(ratios),
            minimum_paired_speedup=min(ratios), maximum_paired_speedup=max(ratios),
            storage_wins=sum(r['sizes'][method] > r['expected_bytes'] for r in rows),
            storage_ties=sum(r['sizes'][method] == r['expected_bytes'] for r in rows))
    report = dict(status='FAIL' if changed else 'PASS', group=group, conditions=len(rows), calls=len(calls),
        all_exact_equal_frozen=True, all_closures_pass=True, input_sha256=inputs, source_changed=changed,
        summary=summary, comparisons=rows, calls_sha256=digest((output / 'calls.json.gz').read_bytes()),
        selections_sha256=digest((output / 'selections.json.gz').read_bytes()),
        qualification=config['qualification'])
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    if changed:
        raise RuntimeError('Benchmark source changed during execution')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=['scientific', 'cloud', 'retinal', 'letter', 'scaling'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=ROOT / 'configs/planner_efficiency_oct26.json')
    args = parser.parse_args()
    run(args.group, args.output, args.protocol)
