"""Constructed real-retinal histories inspired by EyeAI's documented revision."""
from pathlib import Path
import importlib
import time

import numpy as np
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from threadpoolctl import threadpool_limits

from .core import Graph, RestoreError, digest, pack, unpack


def implementation_sha256():
    return digest(Path(__file__).read_bytes())


def execute(op, values, params):
    if params.get('implementation_sha256') != implementation_sha256():
        raise RestoreError('Retinal workflow implementation mismatch')
    with threadpool_limits(limits=1):
        if op == 'retina_features':
            module_name = 'eyeai_legacy' if params['revision'] == 'legacy_shift3' else 'eyeai_current'
            path = Path(__file__).with_name(module_name + '.py')
            if not path.is_file() or digest(path.read_bytes()) != params['entrypoint_sha256']:
                raise RestoreError('Retired or changed retinal feature entry point: ' + module_name)
            shared = Path(__file__).with_name('eyeai_current.py')
            if digest(shared.read_bytes()) != params['shared_feature_sha256']:
                raise RestoreError('Shared retinal feature implementation mismatch')
            return importlib.import_module('recoverml.' + module_name).features(values[0])
        if op == 'retina_train':
            features, labels, split = values
            model = (LogisticRegression(**params['parameters']) if params['estimator'] == 'logistic'
                     else RandomForestClassifier(**params['parameters']))
            model.fit(features[split['train_pixels']], labels.reshape(-1)[split['train_pixels']])
            restored = unpack(pack(model))
            if not np.array_equal(model.predict_proba(features[split['test_pixels']]),
                                  restored.predict_proba(features[split['test_pixels']])):
                raise RestoreError('Native retinal model serialization differs')
            return model
        if op == 'retina_predict':
            model, features, split = values
            return np.ascontiguousarray(model.predict_proba(features[split['test_pixels']])[:, 1])
    raise ValueError('Unknown retinal operation: ' + op)


def load_data(directory, seed, image_size=64, training_pixels=6000):
    directory = Path(directory)
    names = sorted(path.stem for path in (directory / 'stare-images').glob('*.ppm'))
    if len(names) != 20:
        raise ValueError('The study requires all 20 STARE images')
    images, labels = [], []
    for name in names:
        with Image.open(directory / 'stare-images' / (name + '.ppm')) as image:
            images.append(np.asarray(image.convert('RGB').resize((image_size, image_size), Image.Resampling.BILINEAR)))
        with Image.open(directory / 'labels-ah' / (name + '.ah.pgm')) as image:
            labels.append(np.asarray(image.resize((image_size, image_size), Image.Resampling.NEAREST)) > 0)
    images, labels = np.stack(images), np.stack(labels)
    rng = np.random.default_rng(seed)
    order = rng.permutation(20)
    train_images, test_images = np.sort(order[:15]), np.sort(order[15:])
    fov = images.max(axis=-1) > 15
    image_membership = np.broadcast_to(np.arange(20)[:, None, None], fov.shape).reshape(-1)
    train_candidates = np.flatnonzero(fov.reshape(-1) & np.isin(image_membership, train_images))
    test_pixels = np.flatnonzero(fov.reshape(-1) & np.isin(image_membership, test_images)).astype(np.int64)
    train_pixels = np.sort(rng.choice(train_candidates, size=training_pixels, replace=False)).astype(np.int64)
    split = dict(train_images=train_images, test_images=test_images,
                 train_pixels=train_pixels, test_pixels=test_pixels)
    return images, labels, split, names


def capture(directory, estimator, seed, versions, image_size=64, training_pixels=6000):
    if estimator not in ('logistic', 'forest') or versions < 2 or versions % 2:
        raise ValueError('Even historical version count and a supported estimator required')
    images, labels, split, names = load_data(directory, seed, image_size, training_pixels)
    graph, values = Graph(), {}
    code = implementation_sha256()

    def add(op, deps, params, scope, value=None, mandatory=False, version=0):
        params = dict(params, implementation_sha256=code)
        started = time.perf_counter()
        if value is None:
            value = execute(op, [values[dep] for dep in deps], params)
        node = graph.add(op, deps, params, value, not mandatory, scope,
                         time.perf_counter() - started, version, mandatory=mandatory)
        values[node] = value
        return node

    x = add('retina_input', [], dict(kind='images', names=names, size=image_size), 'source', images, True)
    y = add('retina_input', [], dict(kind='labels', annotation='Adam Hoover'), 'source', labels, True)
    membership = add('retina_input', [], dict(kind='image_split', seed=seed), 'source', split, True)
    feature_nodes = {}
    for revision, module in [('legacy_shift3', 'eyeai_legacy'), ('aligned', 'eyeai_current')]:
        feature_nodes[revision] = add('retina_features', [x], dict(revision=revision,
            entrypoint_sha256=digest(Path(__file__).with_name(module + '.py').read_bytes()),
            shared_feature_sha256=digest(Path(__file__).with_name('eyeai_current.py').read_bytes())), 'features')
    if graph.nodes[feature_nodes['legacy_shift3']].blob == graph.nodes[feature_nodes['aligned']].blob:
        raise RestoreError('The injected processing revision did not change feature bytes')
    qualities = []
    for version in range(versions):
        revision = 'legacy_shift3' if version < versions // 2 else 'aligned'
        features = feature_nodes[revision]
        parameters = (dict(C=.2 + .1 * version, max_iter=400, solver='lbfgs', random_state=seed)
                      if estimator == 'logistic' else
                      dict(n_estimators=24, max_depth=8, random_state=seed * 1000 + version, n_jobs=1))
        model = add('retina_train', [features, y, membership], dict(estimator=estimator,
                    parameters=parameters, revision=revision), 'model', version=version)
        prediction = add('retina_predict', [model, features, membership], dict(revision=revision),
                         'prediction', version=version)
        graph.targets[str(version)] = [model, prediction]
        truth = labels.reshape(-1)[split['test_pixels']]
        probabilities = values[prediction]
        qualities.append(dict(version=version, revision=revision,
            auroc=float(roc_auc_score(truth, probabilities)),
            average_precision=float(average_precision_score(truth, probabilities))))
    info = dict(estimator=estimator, seed=seed, versions=versions, images=20,
        image_size=image_size, train_images=split['train_images'].tolist(),
        test_images=split['test_images'].tolist(), training_pixels=len(split['train_pixels']),
        test_pixels=len(split['test_pixels']), image_names=names, quality=qualities,
        feature_nodes=feature_nodes, feature_revision_changes_bytes=True,
        artificially_equal_alternatives=False, implementation_sha256=code,
        data_source='STARE fundus images and Adam Hoover vessel labels',
        qualification='Constructed histories inspired by EyeAI, not its data or clinical task')
    return graph, info


def target_view(graph, mode):
    if mode not in ('model_prediction', 'investigation_features'):
        raise ValueError('Unknown retinal target mode')
    view = Graph(env=graph.env)
    view.nodes, view.archive = dict(graph.nodes), graph.archive
    view.roots = set(graph.roots)
    view.targets = {version: list(targets) for version, targets in graph.targets.items()}
    if mode == 'investigation_features':
        for targets in view.targets.values():
            targets.append(graph.nodes[targets[0]].deps[0])
    return view


def capabilities_for(graph, availability):
    if availability == 'intact':
        return {}, 0
    if availability == 'legacy_removed':
        return {node.id: 'legacy_extractor' for node in graph.nodes.values()
                if node.op == 'retina_features' and node.params['revision'] == 'legacy_shift3'}, 1
    if availability == 'training_prediction_removed':
        return {node.id: node.op for node in graph.nodes.values()
                if node.op in ('retina_train', 'retina_predict')}, 2
    raise ValueError('Unknown retinal availability')
