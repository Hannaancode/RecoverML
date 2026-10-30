"""Verify the permanently archived GitHub runner artifacts and recompute capacity."""

import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tarfile
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
        if set(bundle.namelist()) != {"multi_runner_summary.json", "multi_runner_evidence.tar.gz"}:
            raise ValueError("Action audit artifact members differ")
        with tarfile.open(fileobj=io.BytesIO(bundle.read("multi_runner_evidence.tar.gz")), mode="r:gz") as raw:
            for member in raw.getmembers():
                if member.name == "multi_runner_summary.json" and member.isfile():
                    if raw.extractfile(member).read() != bundle.read("multi_runner_summary.json"):
                        raise ValueError("Duplicate audit summaries differ")
                    continue
                parts = Path(member.name).parts
                if not parts or parts[0] != "multi_runner_download" or ".." in parts:
                    raise ValueError("Unsafe runner evidence path")
                dest = Path(temporary).joinpath(*parts)
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(raw.extractfile(member).read())
                else:
                    raise ValueError("Unexpected runner evidence type")
        result = audit(Path(temporary) / "multi_runner_download")
        if json.loads(json.dumps(result)) != json.loads(bundle.read("multi_runner_summary.json")):
            raise ValueError("Saved multi-runner summary differs from raw requests")
        if result["source_commit"] != "2812e626d634818e6935362741b9c09aecd44f03":
            raise ValueError("Source commit differs")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
