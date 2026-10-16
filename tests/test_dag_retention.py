import copy
import itertools
import random
import unittest

from recoverml.core import Graph
from recoverml.dag_retention import optimize, verify_proof
from recoverml.capability_retention import retained_bytes
from test_capability_retention import independent_can


class DagRetentionTests(unittest.TestCase):
    def test_random_dags_match_brute_force_for_all_small_stores_and_faults(self):
        rng = random.Random(20261016)
        for case in range(64):
            g = Graph(env={}); ids = []; caps = {}
            for i in range(7):
                deps = rng.sample(ids, min(len(ids), rng.randrange(4)))
                nid = g.add('fixture', deps, {'i': i}, ('unique', i),
                            i > 0 and rng.choice([True, True, False]), 'fixture', 0, 0, mandatory=i == 0)
                g.nodes[nid].size = rng.choice([0, 1, 7, 11, 2**54 + 3])
                ids.append(nid)
                if g.nodes[nid].replayable and rng.choice([True, False]): caps[nid] = 'g' + str(i % 3)
            g.targets = {'0': ids[-3:]}
            optional = sorted(g.candidates - g.roots)
            for k in (0, 1, 2):
                groups = sorted(set(caps.values()))
                faults = [f for n in range(min(k, len(groups)) + 1) for f in itertools.combinations(groups, n)]
                best = min(retained_bytes(g, s, caps, k) for flags in itertools.product((False, True), repeat=len(optional))
                    for s in [g.roots | {b for b, flag in zip(optional, flags) if flag}]
                    if all(independent_can(g, s, caps, f) for f in faults))
                chosen, status, diag = optimize(g, caps, k)
                self.assertEqual(status, 'ok')
                self.assertEqual(retained_bytes(g, chosen, caps, k), best)
                self.assertTrue(verify_proof(g, caps, k, chosen, diag['proof']))

    def test_alternative_producers_and_alias_cycles_are_rejected(self):
        g = Graph(env={})
        a = g.add('input', [], {}, 'a', False, '', 0, 0, mandatory=True)
        b = g.add('one', [a], {}, 'b', True, '', 0, 0)
        g.add('two', [a], {}, 'b', True, '', 0, 0)
        g.targets = {'0': [b]}
        self.assertEqual(optimize(g, {}, 0)[1], 'not_applicable')
        g = Graph(env={})
        b = g.add('opaque', [], {}, 'b', False, '', 0, 0)
        g.add('loop', [b], {}, 'b', True, '', 0, 0)
        g.targets = {'0': [b]}
        self.assertEqual(optimize(g, {}, 0)[1], 'not_applicable')

    def test_proof_corruption_is_rejected(self):
        g = Graph(env={}); b = g.add('opaque', [], {}, 'b', False, '', 0, 0)
        g.targets = {'0': [b]}
        selected, _, diag = optimize(g, {}, 0)
        proof = diag['proof']
        for mutate in ('value', 'capacity', 'duplicate', 'missing', 'store'):
            bad = copy.deepcopy(proof); store = set(selected)
            if mutate == 'value': bad['optional_payload_lower_bound'] += 1
            elif mutate == 'capacity': bad['flow'][0][2] += 1
            elif mutate == 'duplicate': bad['flow'].append(bad['flow'][0])
            elif mutate == 'missing': bad['flow'].pop()
            else: store.clear()
            with self.assertRaises(ValueError): verify_proof(g, {}, 0, store, bad)


if __name__ == '__main__': unittest.main()
