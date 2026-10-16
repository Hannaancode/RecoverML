#!/usr/bin/env python3
"""Post-protocol necessity challenge: a closed-form retinal frontier rule."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import time

from recoverml.capability_retention import retained_bytes, restricted
from recoverml.core import Graph
from recoverml.eyeai_workflow import capabilities_for, target_view
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate


def applicable(graph):
    aliases = Counter(node.blob for node in graph.nodes.values())
    if any(count != 1 for count in aliases.values()):
        return False, 'Physical output aliases require separate reasoning'
    features = [node for node in graph.nodes.values() if node.op == 'retina_features']
    if len(features) != 2 or {node.params['revision'] for node in features} != {'legacy_shift3', 'aligned'}:
        return False, 'Expected exactly one old and one new feature output'
    for node in features:
        if not all(graph.nodes[dep].blob in graph.roots for dep in node.deps):
            return False, 'Feature input must be a mandatory root'
    for version, targets in graph.targets.items():
        if len(targets) not in (2, 3):
            return False, 'Unexpected target list'
        model, prediction = (graph.nodes[target] for target in targets[:2])
        if model.op != 'retina_train' or prediction.op != 'retina_predict':
            return False, 'Unexpected target operators'
        if len(model.deps) != 3 or graph.nodes[model.deps[0]].op != 'retina_features':
            return False, 'Unexpected model dependencies'
        if not all(graph.nodes[dep].blob in graph.roots for dep in model.deps[1:]):
            return False, 'Other training dependencies must be mandatory roots'
        if prediction.deps != [model.id, model.deps[0], model.deps[2]]:
            return False, 'Unexpected prediction dependencies'
        if len(targets) == 3 and targets[2] != model.deps[0]:
            return False, 'Unexpected feature investigation target'
    if {node.op for node in graph.nodes.values()} - {'retina_input', 'retina_features', 'retina_train', 'retina_predict'}:
        return False, 'Unexpected operator family'
    return True, 'Two-feature-frontier topology with unique physical outputs'


def closed_form(graph, target_mode, availability):
    roots = set(graph.roots)
    if availability == 'intact':
        return roots
    if availability == 'training_prediction_removed':
        return roots | {node.blob for node in graph.nodes.values()
                        if node.op in ('retina_train', 'retina_predict')}
    if availability != 'legacy_removed':
        raise ValueError('Unknown availability')
    feature = next(node.blob for node in graph.nodes.values() if
                   node.op == 'retina_features' and node.params['revision'] == 'legacy_shift3')
    if target_mode == 'investigation_features':
        return roots | {feature}
    old_targets = {node.blob for node in graph.nodes.values() if
        node.op in ('retina_train', 'retina_predict') and node.params['revision'] == 'legacy_shift3'}
    sizes = graph.sizes()
    return roots | ({feature} if sizes[feature] <= sum(sizes[blob] for blob in old_targets) else old_targets)


def run(directory):
    directory = Path(directory)
    with (directory / 'summary.csv').open() as handle:
        rows = [row for row in csv.DictReader(handle) if row['policy'] == 'RecoverML_exact']
    protocol = json.loads((directory / 'protocol.json').read_text())
    expected = protocol['expected_summary_rows'] // len(protocol['policies'])
    if len(rows) != expected:
        raise RuntimeError('The full exact-comparison grid is required')
    results = []
    for row in rows:
        original = Graph.read(directory / 'captures' / row['capture_id'] / 'manifest.json')
        graph = target_view(original, row['target_mode'])
        valid, reason = applicable(graph)
        if not valid:
            raise RuntimeError('Closed-form proof not applicable: ' + reason)
        caps, k = capabilities_for(graph, row['availability'])
        started = time.perf_counter()
        selected = closed_form(graph, row['target_mode'], row['availability'])
        formula_s = time.perf_counter() - started
        size = retained_bytes(graph, selected, caps, k)
        structural = all(certificate(restricted(graph, caps, fault), selected)['complete']
                         for fault in fault_sets(caps, k))
        results.append(dict(condition_id=row['condition_id'], capture_id=row['capture_id'],
            target_mode=row['target_mode'], availability=row['availability'],
            applicable_proof=True, formula_retained_bytes=size,
            exact_retained_bytes=int(row['retained_bytes']), agrees_with_exact=size == int(row['retained_bytes']),
            structurally_robust=structural, formula_s=formula_s,
            exact_planning_s=float(row['planning_s']), selected=sorted(selected)))
    summary = dict(status='PASS' if all(row['agrees_with_exact'] and row['structurally_robust'] for row in results) else 'FAIL',
        conditions=len(results), matching_exact=sum(row['agrees_with_exact'] for row in results),
        structurally_robust=sum(row['structurally_robust'] for row in results),
        interpretation='This particular retinal topology does not require an exact optimizer. Its useful selective-retention savings can be obtained by a linear scan of one old feature frontier versus old targets.',
        qualification='Post-protocol diagnostic motivated by preflight, not a predeclared sixth method and not a claim of a new algorithm. Formula timing is single-call descriptive and excludes applicability and certificate checks.',
        results=results)
    (directory / 'frontier_formula.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key != 'results'}, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    run(parser.parse_args().directory)
