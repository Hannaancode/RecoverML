"""Capture versioned scikit-learn pipelines, including a controlled opaque boundary."""
import os
import time
import numpy as np
from sklearn.datasets import load_breast_cancer, load_digits, load_wine, make_classification
from .core import Graph, pack
from .operators import execute


def build_history(config: dict, seed: int) -> tuple[Graph, dict]:
    g = Graph()
    values = {}
    tracking_times=[]
    capture_start = time.perf_counter()
    loaders = {'breast_cancer':load_breast_cancer, 'digits':load_digits, 'wine':load_wine}
    if config['dataset'] in loaders:
        data = loaders[config['dataset']]()
        base, y = np.asarray(data.data, dtype=np.float64), data.target
    elif config['dataset'] == 'synthetic':
        base, y = make_classification(n_samples=config['rows'], n_features=20,
                                     n_informative=12, n_redundant=4, random_state=seed)
    else:
        raise ValueError('Unknown dataset: '+str(config['dataset']))
    base = np.ascontiguousarray(base, dtype=np.float64)
    y = np.ascontiguousarray(y, dtype=np.int64)
    def add(op, deps, params, version, scope, value=None, replayable=True, mandatory=False):
        start = time.perf_counter()
        if value is None:
            value = execute(op, [values[d] for d in deps], params)
        elapsed = time.perf_counter() - start
        tracking_start=time.perf_counter()
        nid = g.add(op, deps, params, value, replayable, scope, elapsed, version, mandatory)
        tracking_times.append(time.perf_counter()-tracking_start)
        values[nid] = value
        return nid
    current = base.copy()
    rng = np.random.default_rng(seed + 999)
    stats = []
    for v in range(config['versions']):
        if v and config['change'] == 'data':
            # Mutate a contiguous subset, explicitly revealing block-reuse opportunities.
            count = max(1, int(len(current) * config.get('mutation_fraction', 0.01)))
            start = (v * count) % (len(current) - count + 1)
            current[start:start+count, 0] += rng.normal(0, 0.05, count)
        root_y = add('input', [], {'kind':'labels'}, v, 'source', value=y,
                     replayable=False, mandatory=True)
        blocks = []
        for start in range(0, len(current), config.get('block_rows', 2048)):
            raw = np.ascontiguousarray(current[start:start+config.get('block_rows', 2048)])
            root = add('input', [], {'kind':'features','start':start}, v, 'source',
                       value=raw, replayable=False, mandatory=True)
            blocks.append(add('clean_block', [root], {}, v, 'row-local'))
        x = add('concat', blocks, {}, v, 'global-assembly')
        if config['boundary'] == 'opaque':
            # Emulates an unavailable external enrichment response, not an ordinary
            # random-seeded sklearn operator. Entropy is intentionally NOT retained.
            secret_rng = np.random.default_rng(int.from_bytes(os.urandom(16), 'little'))
            enriched = np.ascontiguousarray(values[x] + secret_rng.normal(0, 0.01, values[x].shape))
            x = add('external_features', [x], {'request_version':v}, v, 'row-local',
                    value=enriched, replayable=False)
        split = add('split', [], {'rows':len(base), 'seed':seed}, v, 'membership')
        scaler = add('fit_scaler', [x,split], {}, v, 'fitted-global')
        scaled = add('scale', [x,scaler], {}, v, 'row-local-given-fitted-state')
        c = 0.5 + v * 0.25 if config['change'] == 'parameters' else 1.0
        targets = []
        accuracy = []
        branches = config.get('branches',1)
        if branches < 1:
            raise ValueError('At least one branch is required')
        scope = config.get('target_scope','model_and_predictions')
        if scope not in ('model_and_predictions','predictions'):
            raise ValueError('Unknown target scope')
        for branch in range(branches):
            model = add('train', [scaled,root_y,split],
                        {'model':config['model'], 'C':c*(1+branch*.5), 'seed':seed+branch,
                         'trees':config.get('trees',12),
                         'depth':config.get('depth',5)+v if config['change']=='parameters' else config.get('depth',6)},
                        v, 'fitted-global')
            pred = add('predict', [model,scaled,split], {}, v, 'row-local-given-model')
            targets.extend([model,pred] if scope=='model_and_predictions' else [pred])
            accuracy.append(float(np.mean(values[model].predict(
                values[scaled][values[split][1]]) == y[values[split][1]])))
        if config.get('protect_intermediate', False):
            targets.append(scaled)
        g.targets[str(v)] = targets
        stats.append({'version':v, 'accuracy':float(np.mean(accuracy)),
                      'branch_accuracy':accuracy})
    elapsed = time.perf_counter() - capture_start
    return g, dict(capture_total_s=elapsed, lineage_serialization_s=sum(tracking_times), operator_total_s=sum(t['capture_s'] for t in g.capture_trace),
                   metadata_and_serialization_s=elapsed-sum(t['capture_s'] for t in g.capture_trace),
                   rows=len(base), version_accuracy=stats)
