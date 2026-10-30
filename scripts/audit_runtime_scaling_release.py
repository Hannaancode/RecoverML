"""Independently recheck the permanently saved Linux scaling artifact."""

import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from benchmark_runtime_scaling import audit


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "results/research/runtime_scaling_oct30/evidence.zip"
ARCHIVE_SHA256 = "dd905bf76b5dceb5949805af440d453612c57b0fc164462ed673a020b80ffe03"
SOURCE_COMMIT = "9adf5f0b4cc808b9d5bd046d5eeb90679d5bfc43"


def main():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Published artifact differs from the Action artifact")
    with tempfile.TemporaryDirectory(prefix="recoverml-scaling-audit-") as directory:
        with zipfile.ZipFile(ARCHIVE) as bundle:
            for member in bundle.infolist():
                path = Path(member.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("Unsafe artifact path")
            bundle.extractall(directory)
        base = Path(directory)
        metadata_commit = (base / "runtime_scaling_metadata/commit.txt").read_text().strip()
        provenance = json.loads((base / "runtime_scaling_full/provenance.json").read_bytes())
        if metadata_commit != SOURCE_COMMIT or provenance["commit"] != SOURCE_COMMIT:
            raise ValueError("Artifact source commit differs")
        full = audit(base / "runtime_scaling_full")
        smoke = audit(base / "runtime_scaling_smoke")
        if (full["status"], full["trials"], full["requests"], full["exact"]) != (
            "PASS", 252, 32256, 32256
        ):
            raise ValueError("Full evidence matrix differs")
        if (smoke["status"], smoke["trials"], smoke["requests"], smoke["exact"]) != (
            "PASS", 8, 64, 64
        ):
            raise ValueError("Smoke evidence matrix differs")
        print(json.dumps(dict(status="PASS", artifact_sha256=ARCHIVE_SHA256,
                              source_commit=SOURCE_COMMIT, full=full, smoke=smoke), indent=2))


if __name__ == "__main__":
    main()
