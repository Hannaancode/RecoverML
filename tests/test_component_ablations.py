"""Validate contract boundaries in the experimental component controls."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_component_ablations import (fixtures, logical_identity,
    no_alternative_producers, no_root_shortcut, scan_certificate, chain_graph)
from recoverml.capability_retention import optimize, retained_bytes
from recoverml.component_retention import optimize as decomposed
from recoverml.witness import certificate


class ComponentAblationTests(unittest.TestCase):
    def test_disabled_atomic_shortcut_preserves_same_optimal_bytes(self):
        for graph, caps, k in fixtures().values():
            expected, status, _ = decomposed(graph, caps, k)
            chosen, changed_status, _ = no_root_shortcut(graph, caps, k, 10.)
            self.assertEqual((status, changed_status), ("ok", "ok"))
            self.assertEqual(retained_bytes(graph, expected, caps, k), retained_bytes(graph, chosen, caps, k))

    def test_removed_alternative_is_explicitly_a_different_contract(self):
        graph, caps, k = fixtures()["alternative_producers"]
        original, _, _ = optimize(graph, caps, k)
        changed, changed_caps = no_alternative_producers(graph, caps)
        selected, status, _ = optimize(changed, changed_caps, k)
        self.assertEqual(status, "ok")
        self.assertEqual(original, graph.roots)
        self.assertGreater(len(selected-changed.roots), 0)
        self.assertEqual(set(changed.nodes), set(graph.nodes))

    def test_logical_identity_and_reference_certificate_boundaries(self):
        graph, caps, _ = fixtures()["alternative_producers"]
        changed, _ = logical_identity(graph, caps)
        self.assertEqual(len(changed.candidates), len(graph.nodes))
        self.assertGreater(len(changed.candidates), len(graph.candidates))
        chain = chain_graph(128)
        reference = scan_certificate(chain, chain.roots)
        indexed = certificate(chain, chain.roots)
        self.assertEqual(set(reference["available"]), set(indexed["available"]))
        self.assertEqual(reference["version_coverage"], indexed["version_coverage"])


if __name__ == "__main__":
    unittest.main()
