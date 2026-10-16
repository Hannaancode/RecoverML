"""Fixed constructed histories adapted from public sklearn pipeline recipes.

These are executable recipe adaptations, not independently collected production
histories. Every recipe has one preprocessing path and ordinary hyperparameter
versions; no equal-output alternative producer is deliberately constructed.
Transformers fit on the training partition only. Targets are fitted inference
state and held-out predictions, not resumable training optimizer state.

Public recipe inspirations (sklearn 1.8):
https://scikit-learn.org/1.8/auto_examples/compose/plot_feature_union.html
https://scikit-learn.org/1.8/auto_examples/compose/plot_compare_reduction.html
The diabetes polynomial regression and digits forest are explicitly constructed
adaptations of these composition patterns, not reproductions of those examples.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import time

import numpy as np
from sklearn.datasets import load_diabetes, load_digits, load_iris
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, chi2, f_classif
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, PolynomialFeatures, StandardScaler
from sklearn.svm import LinearSVC, SVC
from threadpoolctl import threadpool_limits

from .core import Graph, RestoreError, digest, pack, unpack


WORKFLOWS = ('iris_union', 'digits_pca', 'diabetes_poly', 'digits_forest')
_CHECKPOINT_KIND = 'scientific_sklearn_inference_v1'


def implementation_sha256():
    return digest(Path(__file__).read_bytes())


def _new_estimator(name, parameters):
    factories = dict(pca=PCA, minmax=MinMaxScaler, standard=StandardScaler,
                     polynomial=PolynomialFeatures, svc=SVC,
                     linear_svc=LinearSVC, ridge=Ridge,
                     forest=RandomForestClassifier)
    if name == 'select_f':
        return SelectKBest(score_func=f_classif, **parameters)
    if name == 'select_chi2':
        return SelectKBest(score_func=chi2, **parameters)
    try:
        return factories[name](**parameters)
    except KeyError as exc:
        raise ValueError('Unknown scientific workflow estimator: ' + name) from exc


def _checkpoint(model, name, parameters):
    """Record numeric fitted state without pickle object-reference identities.

    Supported forest state uses the project's existing exact tree codec. Other
    listed estimators use their numeric fitted state with an explicit class
    allowlist. Constructor callables such as SelectKBest.score_func are selected
    by the recorded recipe name, never serialized as executable payloads.
    """
    if name == 'forest':
        return model
    constructor_keys = set(model.get_params(deep=False))
    state = {key: value for key, value in model.__dict__.items()
             if key not in constructor_keys}
    # BLAS dispatch can depend on C versus Fortran layout even when the numbers
    # are identical. PCA components are commonly Fortran contiguous, so retain
    # this property explicitly instead of silently changing low-order bits.
    fortran_arrays = sorted(key for key, value in state.items()
                            if isinstance(value, np.ndarray) and value.ndim > 1
                            and value.flags.f_contiguous and not value.flags.c_contiguous)
    return dict(recoverml_checkpoint=1, kind=_CHECKPOINT_KIND,
                implementation_sha256=implementation_sha256(),
                estimator=name, parameters=dict(parameters), fitted_state=state,
                fortran_arrays=fortran_arrays)


def restore_estimator(checkpoint):
    if isinstance(checkpoint, RandomForestClassifier):
        return checkpoint
    if not isinstance(checkpoint, dict) or checkpoint.get('kind') != _CHECKPOINT_KIND:
        raise RestoreError('Unsupported scientific workflow checkpoint')
    if checkpoint.get('implementation_sha256') != implementation_sha256():
        raise RestoreError('Scientific workflow checkpoint implementation mismatch')
    estimator = _new_estimator(checkpoint['estimator'], checkpoint['parameters'])
    estimator.__dict__.update(checkpoint['fitted_state'])
    for key in checkpoint['fortran_arrays']:
        estimator.__dict__[key] = np.asfortranarray(estimator.__dict__[key])
    return estimator


def execute(op, values, params):
    """Replay a declared recipe operator under its exact implementation contract."""
    if params.get('implementation_sha256') != implementation_sha256():
        raise RestoreError('Scientific workflow implementation contract mismatch')
    with threadpool_limits(limits=1):
        if op == 'scientific_split':
            x, y = values
            train, test = train_test_split(
                np.arange(len(x), dtype=np.int64), test_size=.25,
                random_state=params['seed'],
                stratify=y if params['classification'] else None)
            return (np.ascontiguousarray(train), np.ascontiguousarray(test))
        if op == 'scientific_fit_transformer':
            x, y, split = values
            model = _new_estimator(params['estimator'], params['parameters'])
            train = split[0]
            if params['estimator'] in ('select_f', 'select_chi2'):
                model.fit(x[train], y[train])
            else:
                model.fit(x[train])
            checkpoint = _checkpoint(model, params['estimator'], params['parameters'])
            restored = restore_estimator(unpack(pack(checkpoint)))
            if not np.array_equal(model.transform(x), restored.transform(x)):
                raise RestoreError('Scientific transformer native output differs')
            return checkpoint
        if op == 'scientific_transform':
            x, checkpoint = values
            return np.ascontiguousarray(restore_estimator(checkpoint).transform(x))
        if op == 'scientific_union':
            return np.ascontiguousarray(np.concatenate(values, axis=1))
        if op == 'scientific_train':
            x, y, split = values
            model = _new_estimator(params['estimator'], params['parameters'])
            model.fit(x[split[0]], y[split[0]])
            checkpoint = _checkpoint(model, params['estimator'], params['parameters'])
            restored = restore_estimator(unpack(pack(checkpoint)))
            if not np.array_equal(model.predict(x[split[1]]), restored.predict(x[split[1]])):
                raise RestoreError('Scientific model native predictions differ')
            return checkpoint
        if op == 'scientific_predict':
            checkpoint, x, split = values
            return np.ascontiguousarray(restore_estimator(checkpoint).predict(x[split[1]]))
    raise ValueError('Unknown scientific workflow operator: ' + op)


def capture(name, seed, versions=3):
    """Capture one frozen public-recipe history and its held-out quality checks.

    Versions select a prefix of three predeclared configurations; this function
    performs no hyperparameter search or selection using recovery results.
    """
    if name not in WORKFLOWS:
        raise ValueError('Unknown scientific workflow: ' + name)
    if not isinstance(versions, int) or isinstance(versions, bool) or not 1 <= versions <= 3:
        raise ValueError('Scientific workflows require 1 to 3 fixed versions')
    classification = name != 'diabetes_poly'
    dataset_name = 'iris' if name == 'iris_union' else 'diabetes' if not classification else 'digits'
    dataset = dict(iris=load_iris, digits=load_digits, diabetes=load_diabetes)[dataset_name]()
    x = np.ascontiguousarray(dataset.data, dtype=np.float64)
    y = np.ascontiguousarray(dataset.target, dtype=np.int64 if classification else np.float64)
    graph, values = Graph(), {}
    code_hash = implementation_sha256()

    def add(op, deps, parameters, scope, *, value=None, version=0, mandatory=False):
        params = dict(parameters, implementation_sha256=code_hash)
        started = time.perf_counter()
        if value is None:
            value = execute(op, [values[dependency] for dependency in deps], params)
        node = graph.add(op, deps, params, value, not mandatory, scope,
                         time.perf_counter() - started, version, mandatory=mandatory)
        values[node] = value
        return node

    rx = add('input', [], dict(dataset=dataset_name, kind='x'), 'source', value=x, mandatory=True)
    ry = add('input', [], dict(dataset=dataset_name, kind='y'), 'source', value=y, mandatory=True)
    split = add('scientific_split', [rx, ry], dict(seed=int(seed), classification=classification), 'membership')

    def transform(input_node, estimator, parameters):
        spec = dict(estimator=estimator, parameters=parameters)
        fitted = add('scientific_fit_transformer', [input_node, ry, split], spec, 'preprocessing')
        return add('scientific_transform', [input_node, fitted], spec, 'preprocessing')

    if name == 'iris_union':
        pca = transform(rx, 'pca', dict(n_components=2, svd_solver='full'))
        selected = transform(rx, 'select_f', dict(k=1))
        features = add('scientific_union', [pca, selected], dict(estimator='feature_union'), 'preprocessing')
        estimator = 'svc'
        configurations = [dict(C=c, kernel='linear', random_state=int(seed)) for c in (.1, 1., 10.)]
        recipe_source = 'https://scikit-learn.org/1.8/auto_examples/compose/plot_feature_union.html'
    elif name == 'digits_pca':
        scaled = transform(rx, 'minmax', dict())
        features = transform(scaled, 'pca', dict(n_components=8, svd_solver='full'))
        estimator = 'linear_svc'
        configurations = [dict(C=c, dual=False, max_iter=10000, random_state=int(seed))
                          for c in (.1, 1., 10.)]
        recipe_source = 'https://scikit-learn.org/1.8/auto_examples/compose/plot_compare_reduction.html'
    elif name == 'diabetes_poly':
        scaled = transform(rx, 'standard', dict())
        features = transform(scaled, 'polynomial', dict(degree=2, include_bias=False))
        estimator = 'ridge'
        configurations = [dict(alpha=alpha, solver='svd') for alpha in (.1, 1., 10.)]
        recipe_source = 'constructed adaptation: StandardScaler + PolynomialFeatures(degree=2) + Ridge'
    else:
        scaled = transform(rx, 'minmax', dict())
        features = transform(scaled, 'select_chi2', dict(k=32))
        estimator = 'forest'
        configurations = [dict(n_estimators=trees, random_state=int(seed), n_jobs=1)
                          for trees in (64, 128, 256)]
        recipe_source = 'constructed adaptation: MinMaxScaler + SelectKBest(chi2, k=32) + RandomForestClassifier'

    qualities, model_bytes, model_hashes, prediction_hashes = [], [], [], []
    for version, parameters in enumerate(configurations[:versions]):
        model = add('scientific_train', [features, ry, split],
                    dict(estimator=estimator, parameters=parameters), 'model', version=version)
        prediction = add('scientific_predict', [model, features, split],
                         dict(estimator=estimator), 'prediction', version=version)
        graph.targets[str(version)] = [model, prediction]
        pred = values[prediction]
        if not np.isfinite(pred).all():
            raise RestoreError('Nonfinite scientific workflow predictions')
        target = y[values[split][1]]
        qualities.append(float(accuracy_score(target, pred) if classification else r2_score(target, pred)))
        model_bytes.append(graph.nodes[model].size)
        model_hashes.append(graph.nodes[model].blob)
        prediction_hashes.append(graph.nodes[prediction].blob)
    counts = Counter(node.blob for node in graph.nodes.values())
    return graph, dict(
        workflow=name, dataset=dataset_name, seed=int(seed), versions=versions,
        rows=len(x), columns=x.shape[1], transformed_columns=values[features].shape[1],
        train_rows=len(values[split][0]), test_rows=len(values[split][1]),
        source_x_sha256=digest(pack(x)), source_y_sha256=digest(pack(y)),
        split_sha256=graph.nodes[split].blob, implementation_sha256=code_hash,
        recipe_source=recipe_source, declared_configurations=configurations[:versions],
        classification=classification, quality_metric='accuracy' if classification else 'r2',
        quality=qualities, model_bytes=model_bytes, largest_model_bytes=max(model_bytes),
        model_sha256=model_hashes, prediction_sha256=prediction_hashes,
        native_prediction_check=True, training_partition_only_fit=True,
        deliberately_equal_alternatives=False,
        naturally_aliased_blob_count=sum(count > 1 for count in counts.values()),
        qualification='Fixed constructed public-recipe adaptations; not production workflow traces; inference state targets')


def caps_for(graph, scope='preprocessing'):
    """Declare correlated capability loss groups before retention optimization.

    A transform family includes both its fit and transform operators. Membership
    is a separate group. Broad scope additionally covers model fitting and
    prediction. None of these groups models deletion of retained files.
    """
    if scope not in ('preprocessing', 'broad'):
        raise ValueError('Scientific capability scope must be preprocessing or broad')
    capabilities = {}
    for node in graph.nodes.values():
        if not node.replayable:
            continue
        if node.op == 'scientific_split':
            capabilities[node.id] = 'split_membership'
        elif node.op in ('scientific_fit_transformer', 'scientific_transform', 'scientific_union'):
            capabilities[node.id] = 'preprocess:' + node.params['estimator']
        elif scope == 'broad' and node.op == 'scientific_train':
            capabilities[node.id] = 'model_training'
        elif scope == 'broad' and node.op == 'scientific_predict':
            capabilities[node.id] = 'prediction'
    return capabilities
