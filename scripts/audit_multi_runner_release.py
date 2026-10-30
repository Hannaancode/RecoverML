"""Verify the permanently archived GitHub runner artifacts and recompute capacity."""

import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

from audit_multi_runner_replica import audit


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "results/research/multi_runner_oct30"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    archive = RELEASE / "evidence.zip"
    expected = (RELEASE / "evidence.sha256").read_text().strip()
    if sha(archive.read_bytes()) != expected:
        raise ValueError("Multi-runner release archive hash differs")
    with zipfile.ZipFile(archive) as bundle, TemporaryDirectory() as temporary:
        index = json.loads(bundle.read("artifact_index.json"))
        if index["run_id"] != 41037831235 or len(index["artifacts"]) != 7:
            raise ValueError("Runner index differs")
        for item in index["artifacts"]:
            data = bundle.read("artifacts/" + item["name"] + ".zip")
            if sha(data) != item["sha256"]:
                raise ValueError("GitHub artifact ZIP hash differs")
            dest = Path(temporary) / item["name"]
            dest.mkdir()
            with zipfile.ZipFile(io.BytesIO(data)) as member_archive:
                for member in member_archive.infolist():
                    if Path(member.filename).name != member.filename or member.is_dir():
                        raise ValueError("Unexpected artifact member path")
                    (dest / member.filename).write_bytes(member_archive.read(member))
        result = audit(temporary)
        if json.loads(json.dumps(result)) != json.loads(bundle.read("audit_summary.json")):
            raise ValueError("Saved multi-runner summary differs from raw requests")
        if result["source_commit"] != index["source_commit"]:
            raise ValueError("Source commit differs")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
