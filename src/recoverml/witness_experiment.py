"""Controlled artifact witness experiment on two new public datasets.

Equal outputs are deliberately constructed to test the mechanism, not claimed
to be naturally frequent. Changed and absent witnesses are negative controls.
An exhaustive storage search supplies both baseline and new-policy optima.
"""
import argparse
import itertools
import json
import time
from pathlib import Path
import numpy as np
from sklearn.datasets import load_breast_cancer, load_diabetes
from threadpoolctl import threadpool_limits
from .core import Graph, DiskRestorer, RestoreError, digest, pack, write_store
from .operators import execute
from .witness import certificate, WitnessRestorer


def run(destination):
    destination.mkdir(parents=True, exist_ok=False)
    rows, traces, datasets = [], [], []
    with threadpool_limits(limits=1):
        for name, loader in [('breast_cancer', load_breast_cancer), ('diabetes', load_diabetes)]:
            source = np.ascontiguousarray(loader().data, dtype=np.float64)
            datasets.append(dict(name=name, rows=len(source), columns=source.shape[1],
                                 packed_sha256=digest(pack(source))))
            for seed in range(10):
                x = np.ascontiguousarray(source[np.random.default_rng(seed).permutation(len(source))])
                for control in ('exact', 'changed', 'absent'):
                    g = Graph()
                    root = g.add('input', [], {}, x, False, 'root', 0., seed, mandatory=True)
                    for version in range(3):
                        params = dict(scale=1.+(version+1)/8, offset=(seed+1)/16)
                        started = time.perf_counter(); output = execute('affine_features', [x], params)
                        duration = time.perf_counter()-started
                        target = g.add('external_features', [root], {'version': version},
                                       output, False, 'external', duration, version)
                        if control != 'absent':
                            alternative_params = dict(params)
                            if control == 'changed': alternative_params['offset'] += 1e-5
                            started = time.perf_counter()
                            alternative = execute('affine_features', [x], alternative_params)
                            g.add('affine_features', [root], alternative_params, alternative,
                                  True, 'pure_alternative', time.perf_counter()-started, version)
                        g.targets[str(version)] = [target]
                    optional = sorted(g.candidates-g.roots)
                    best = {}
                    for policy in ('logical', 'witness'):
                        for bits in itertools.product([False, True], repeat=len(optional)):
                            retained = g.roots | {b for b, flag in zip(optional, bits) if flag}
                            covered = (g.coverage(retained)[0] if policy == 'logical'
                                       else certificate(g, retained)['complete'])
                            if covered and (policy not in best or g.size(retained) < best[policy][0]):
                                best[policy] = (g.size(retained), retained)
                    case = f'{name}-{seed:02d}-{control}'
                    stores = {}
                    for policy, (size, retained) in best.items():
                        store = destination/'stores'/case/policy
                        write_store(g, retained, store); stores[policy] = store
                        for version, targets in g.targets.items():
                            disk = Graph.read(store/'manifest.json')
                            restorer = (DiskRestorer(disk, store) if policy == 'logical'
                                        else WitnessRestorer(disk, store))
                            started_ns = time.time_ns()
                            values = restorer.version(version)
                            exact = all(pack(value) == g.archive[g.nodes[t].blob]
                                        for t, value in zip(targets, values))
                            if not exact: raise RuntimeError('Recovery mismatch')
                            traces.append(dict(case=case, policy=policy, version=version,
                                start_timestamp_ns=started_ns, end_timestamp_ns=time.time_ns(),
                                exact=exact, events=restorer.trace))
                    # Equal storage comparison: baseline executor on witness-selected store.
                    baseline_at_witness_budget = 0
                    for version in g.targets:
                        try:
                            DiskRestorer(Graph.read(stores['witness']/'manifest.json'), stores['witness']).version(version)
                            baseline_at_witness_budget += 1
                        except RestoreError:
                            pass
                    rows.append(dict(case=case, dataset=name, seed=seed, control=control,
                        manifest_bytes=g.metadata_bytes(), root_bytes=sum(g.sizes()[b] for b in g.roots),
                        logical_minimum_bytes=best['logical'][0], witness_minimum_bytes=best['witness'][0],
                        saved_bytes=best['logical'][0]-best['witness'][0],
                        baseline_at_witness_budget=baseline_at_witness_budget,
                        witness_at_witness_budget=len(g.targets)))
    import csv
    with (destination/'summary.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (destination/'execution_traces.json').write_text(json.dumps(traces, indent=2)+'\n')
    summary = dict(cases=len(rows), exact_restores=len(traces),
        controlled_duplicate_cases=sum(r['control']=='exact' for r in rows),
        controls=['changed bytes', 'no alternative producer'], datasets=datasets,
        source_sha256=digest(Path(__file__).read_bytes()),
        witness_source_sha256=digest(Path(__file__).with_name('witness.py').read_bytes()),
        qualification='Controlled feature-level exact duplicates; not neural training gains or natural frequency evidence')
    (destination/'provenance.json').write_text(json.dumps(summary, indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7,4))
    controls = ['exact','changed','absent']
    savings = [np.mean([100*r['saved_bytes']/r['logical_minimum_bytes'] for r in rows if r['control']==c]) for c in controls]
    ax.bar(controls,savings); ax.set_ylabel('Total stored bytes saved (%)')
    ax.set_xlabel('Controlled alternative producer condition')
    ax.set_title('Exact artifact witnesses on two public datasets')
    fig.tight_layout(); fig.savefig(destination/'storage_savings.png',dpi=180); plt.close(fig)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
