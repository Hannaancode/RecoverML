"""Process-crash and concurrent-reader checks for immutable stores."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from recoverml.core import digest
from recoverml.file_export import export_retained_targets
from recoverml.store_publish import publish_store, verify_published_store


class SmallGraph:
    def __init__(self):
        raw = [b"recoverml-first-payload", b"recoverml-second-payload"]
        self.archive = {digest(value): value for value in raw}
        self.roots = {digest(raw[0])}
        self.targets = {"0": ["target"]}

    def sizes(self):
        return {key: len(value) for key, value in self.archive.items()}

    def manifest(self):
        blobs = list(self.archive)
        return dict(schema=1, environment={}, mandatory_blobs=sorted(self.roots),
                    targets=self.targets,
                    nodes=[dict(id="root", blob=blobs[0], size=len(self.archive[blobs[0]])),
                           dict(id="target", blob=blobs[1], size=len(self.archive[blobs[1]]))])


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.graph = SmallGraph()
        self.selected = set(self.graph.archive)

    def child(self, stage, destination):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        return subprocess.run([sys.executable, __file__, "--crash", stage, str(destination)],
                              env=env, capture_output=True, text=True)

    def test_process_crash_before_and_after_publication(self):
        for stage in ("staged", "published"):
            with self.subTest(stage=stage):
                destination = self.base / stage
                result = self.child(stage, destination)
                self.assertEqual(result.returncode, 47, result.stderr)
                if stage == "staged":
                    self.assertFalse(destination.exists())
                    self.assertEqual(len(list(self.base.glob(f".{stage}.staging-*"))), 1)
                else:
                    self.assertEqual(verify_published_store(destination, self.selected)["status"], "PASS")

    def test_concurrent_readers_have_isolated_outputs(self):
        destination = self.base / "published"
        publish_store(self.graph, self.selected, destination)
        target = self.graph.manifest()["nodes"][1]["blob"]

        def read(index):
            output = self.base / f"request-{index}"
            result = export_retained_targets(destination, output, target_ids=["target"])
            return result["target_sha256"], digest((output / f"{target}.pkl").read_bytes())

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(read, range(32)))
        self.assertTrue(all(receipt == {target: target} and observed == target
                            for receipt, observed in outcomes))

    def test_existing_destination_is_unchanged(self):
        destination = self.base / "published"
        publish_store(self.graph, self.selected, destination)
        original = (destination / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            publish_store(self.graph, self.selected, destination)
        self.assertEqual((destination / "manifest.json").read_bytes(), original)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--crash":
        _, _, stage, destination = sys.argv
        graph = SmallGraph()

        def crash(at):
            if at == stage:
                os._exit(47)

        publish_store(graph, set(graph.archive), Path(destination), checkpoint=crash)
    else:
        unittest.main()
