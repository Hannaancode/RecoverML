import itertools
import random
import tempfile
import unittest
from pathlib import Path
import numpy as np
from recoverml.core import Graph, RestoreError, pack, write_store
from recoverml.witness import certificate, WitnessRestorer


class WitnessTests(unittest.TestCase):
    def example(self):
        g = Graph(env={})
        x = np.arange(8, dtype=float)
        root = g.add('input', [], {}, x, False, 'root', 0., 0, mandatory=True)
        params = dict(scale=2., offset=1.)
        value = np.ascontiguousarray(x*2.+1.)
        pure = g.add('affine_features', [root], params, value, True, 'pure', .01, 0)
        opaque = g.add('external_features', [root], {}, value, False, 'external', .01, 0)
        g.targets = {'0': [opaque]}
        return g, root, pure, opaque

    def test_opaque_artifact_recovers_without_replaying_opaque_event(self):
        g, _, pure, target = self.example()
        self.assertFalse(g.coverage(g.roots)[0])
        self.assertTrue(certificate(g, g.roots)['complete'])
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp)/'store'
            write_store(g, g.roots, store)
            disk = Graph.read(store/'manifest.json')
            self.assertEqual(disk.archive, {})
            restorer = WitnessRestorer(disk, store, verify_environment=False)
            self.assertEqual(pack(restorer.get(target)), g.archive[g.nodes[target].blob])
            self.assertEqual(restorer.trace[-1]['producer'], pure)
            self.assertTrue(restorer.trace[-1]['alternative'])

    def test_self_supporting_alias_cycle_is_not_recoverable(self):
        g = Graph(env={})
        root = g.add('input', [], {}, 1, False, 'root', 0., 0)
        same = g.add('affine_features', [root], dict(scale=1, offset=0), 1,
                     True, 'identity', .01, 0)
        g.targets = {'0': [same]}
        self.assertFalse(certificate(g, set())['complete'])
        self.assertTrue(certificate(g, {g.nodes[root].blob})['complete'])

    def test_mismatched_contract_fails_hash_check(self):
        g, _, pure, target = self.example()
        g.nodes[pure].params['offset'] = 2.
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp)/'store'; write_store(g, g.roots, store)
            with self.assertRaisesRegex(RestoreError, 'hash mismatch'):
                WitnessRestorer(g, store, verify_environment=False).get(target)

    def test_corruption_fails_closed(self):
        g, _, _, target = self.example()
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp)/'store'; write_store(g, g.candidates, store)
            (store/'blobs'/(g.nodes[target].blob+'.pkl')).write_bytes(b'corrupt')
            with self.assertRaisesRegex(RestoreError, 'Corrupt'):
                WitnessRestorer(g, store, verify_environment=False).get(target)

    def test_fixed_point_against_independent_path_oracle(self):
        rng = random.Random(431)
        checked = 0
        for case in range(64):
            g = Graph(env={}); ids = []
            for i in range(7):
                deps = rng.sample(ids, min(len(ids), rng.randrange(3)))
                ids.append(g.add('test', deps, {'i': i}, rng.randrange(6),
                                 rng.choice([True, False]), str(i), .01, case))
            g.targets = {'0': ids[-2:]}
            producers = {}
            for n in g.nodes.values():
                if n.replayable:
                    producers.setdefault(n.blob, []).append(n)
            def possible(blob, retained, path):
                if blob in retained: return True
                if blob in path: return False
                return any(all(possible(g.nodes[d].blob, retained, path | {blob})
                               for d in n.deps) for n in producers.get(blob, []))
            blobs = sorted(g.candidates)
            for bits in itertools.product([False, True], repeat=len(blobs)):
                retained = {b for b, selected in zip(blobs, bits) if selected}
                expected = all(possible(g.nodes[t].blob, retained, set()) for t in ids[-2:])
                self.assertEqual(certificate(g, retained)['complete'], expected)
                checked += 1
        self.assertGreater(checked, 1000)
