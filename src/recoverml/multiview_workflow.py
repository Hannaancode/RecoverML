"""Exploratory two-view classification histories, not production traces.

The interacting choice is retaining both input views versus many fitted
models and predictions. A concat-materialization control tests whether this
advantage disappears when a shared joint matrix is captured explicitly.
"""
from pathlib import Path
import time

import numpy as np
from sklearn.datasets import load_breast_cancer, load_wine
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .core import Graph, RestoreError, digest, pack, unpack


def code_hash():
    return digest(Path(__file__).read_bytes())


def execute(op, values, p):
    if p.get('implementation_sha256') != code_hash():
        raise RestoreError('Multiview implementation mismatch')
    with threadpool_limits(limits=1):
        if op == 'view_standardize':
            x, split = values
            columns = np.array(p['columns'])
            # Train-only fit; each view is a complete deterministic processing
            # stage and its fitted scaler is internal to this declared stage.
            scaler = StandardScaler().fit(x[split[0]][:, columns])
            return np.ascontiguousarray(scaler.transform(x[:, columns]))
        if op == 'view_concat':
            return np.ascontiguousarray(np.concatenate(values, axis=1))
        if op == 'view_train':
            *views, y, split = values
            x = np.concatenate(views, axis=1)
            model = LogisticRegression(C=p['C'], solver='lbfgs', max_iter=2000,
                                       tol=1e-9, random_state=p['seed'])
            model.fit(x[split[0]], y[split[0]])
            return model
        if op == 'view_predict':
            model, *views, split = values
            x = np.concatenate(views, axis=1)
            return np.ascontiguousarray(model.predict_proba(x[split[1]]))
    raise ValueError('Unsupported multiview operation: ' + op)


def capture(dataset, seed, versions, materialize_concat):
    if dataset not in ('wine', 'breast_cancer') or versions not in (4, 16, 64):
        raise ValueError('Outside frozen experiment grid')
    data = {'wine': load_wine, 'breast_cancer': load_breast_cancer}[dataset]()
    x = np.ascontiguousarray(data.data, dtype=np.float64)
    y = np.ascontiguousarray(data.target, dtype=np.int64)
    train, test = train_test_split(np.arange(len(y), dtype=np.int64),
        test_size=.25, random_state=seed, stratify=y)
    split = (np.ascontiguousarray(train), np.ascontiguousarray(test))
    graph = Graph(); values = {}; caps = {}; signature = code_hash(); quality = []

    def add(op, deps, parameters, value=None, mandatory=False, version=0):
        parameters = dict(parameters, implementation_sha256=signature)
        clock = time.perf_counter()
        if value is None:
            value = execute(op, [values[d] for d in deps], parameters)
        nid = graph.add(op, deps, parameters, value, not mandatory, op,
                        time.perf_counter()-clock, version, mandatory=mandatory)
        values[nid] = value
        return nid

    source = add('input', [], {'dataset': dataset}, x, True)
    labels = add('input', [], {'kind': 'labels'}, y, True)
    membership = add('input', [], {'kind': 'split', 'seed': seed}, split, True)
    # Disjoint column views use all input features without selecting dimensions
    # or precision after observing storage results.
    views = []
    for index, columns in enumerate(np.array_split(np.arange(x.shape[1]), 2)):
        nid = add('view_standardize', [source, membership], {'columns': columns.tolist()})
        caps[nid] = 'preprocessing_view_' + str(index)
        views.append(nid)
    feature_ids = list(views)
    if materialize_concat:
        views = [add('view_concat', views, {})]
    # Every history independently spans the same fixed regularization range.
    for version, c in enumerate(np.logspace(-3, 3, versions)):
        parameters = {'C': float(c), 'seed': seed}
        model = add('view_train', views + [labels, membership], parameters, version=version)
        prediction = add('view_predict', [model] + views + [membership], {}, version=version)
        graph.targets[str(version)] = [model, prediction]
        restored = unpack(pack(values[model]))
        transformed = np.concatenate([values[n] for n in views], axis=1)
        if not np.array_equal(restored.predict_proba(transformed[test]), values[prediction]):
            raise RuntimeError('Captured checkpoint does not preserve native probabilities')
        quality.append(dict(version=version, C=float(c), accuracy=accuracy_score(y[test],
            restored.classes_[values[prediction].argmax(axis=1)])))
    return graph, caps, dict(dataset=dataset, seed=seed, versions=versions,
        materialize_concat=materialize_concat, rows=len(y), columns=x.shape[1],
        train_rows=len(train), test_rows=len(test), feature_nodes=feature_ids,
        all_versions_used=True, quality=quality)
