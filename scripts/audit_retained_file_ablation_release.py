"""Independently audit the archived same-store recovery ablation."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from benchmark_retained_file_ablation import audit


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "results/research/retained_file_ablation_oct30/evidence.zip"
EXPECTED_SHA256 = "e63c3c104c29683d56580de22f55203a6eb152d1be4b2374b991cf35ef0732a6"
EXPECTED_COMMIT = "9d830e28696be54a41c0c4068c5bb7ecf166542b"


def main():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Ablation archive digest differs from the published run")
    with TemporaryDirectory() as temp:
        with ZipFile(ARCHIVE) as zipped:
            for name in zipped.namelist():
                path = Path(name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("Unsafe ablation archive member")
            zipped.extractall(temp)
        full = Path(temp) / "retained-file-ablation-full"
        result = audit(full)
        provenance = json.loads((full / "provenance.json").read_bytes())
        if provenance["source_commit"] != EXPECTED_COMMIT:
            raise ValueError("Ablation source commit differs")
        if (result["trials"], result["requests"], result["exact"]) != (54, 3456, 3456):
            raise ValueError("Ablation matrix or exact recovery count differs")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
