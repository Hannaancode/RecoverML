import tempfile
import unittest
from pathlib import Path
from threadpoolctl import threadpool_limits

from recoverml.core import Graph, pack, write_store
from recoverml.capability_retention import restricted
from recoverml.dag_retention import optimize
from recoverml.multiview_workflow import capture, execute
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import WitnessRestorer


class MultiviewTests(unittest.TestCase):
    def test_real_payloads_restore_after_each_declared_view_loss(self):
        with threadpool_limits(limits=1):
            for concat in (False, True):
                graph, caps, info = capture('wine', 20261016, 4, concat)
                selected, status, _ = optimize(graph, caps, 1)
                self.assertEqual(status, 'ok')
                self.assertEqual(len(info['quality']), 4)
                with tempfile.TemporaryDirectory() as temporary:
                    store = Path(temporary) / 'store'; write_store(graph, selected, store)
                    for lost in fault_sets(caps, 1):
                        disk = restricted(Graph.read(store/'manifest.json'), caps, lost)
                        self.assertFalse(disk.archive)
                        for version, targets in graph.targets.items():
                            values = WitnessRestorer(disk, store, replay_execute=execute).version(version)
                            self.assertTrue(all(pack(value) == graph.archive[graph.nodes[t].blob]
                                                for value, t in zip(values, targets)))


if __name__ == '__main__': unittest.main()
