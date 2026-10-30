"""Publish an immutable selected store at one final path.

The caller assigns one publisher to each destination. Readers use only the
final path, never a sibling staging directory. This provides atomic visibility
for process crashes on one filesystem; it is not a distributed transaction.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Mapping

from .core import canonical, digest


def _write_synced(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_store(graph, retained: set[str], destination: Path,
                  *, extra_files: Mapping[str, bytes] | None = None,
                  checkpoint: Callable[[str], None] | None = None) -> None:
    """Write and verify a store before atomically exposing its directory.

    ``checkpoint`` is for crash injection in tests. It receives ``staged``
    after all bytes are durable in the staging directory and ``published``
    immediately after rename. A process kill may leave an unreferenced staging
    directory; it never makes that directory a readable final store.
    """
    destination = Path(destination)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    selected = sorted(set(retained))
    if not graph.roots <= set(selected):
        raise ValueError("Mandatory roots are missing from the selected store")
    sizes = graph.sizes()
    if not set(selected) <= sizes.keys():
        raise ValueError("Selected store has an unknown blob")
    manifest = canonical(graph.manifest())
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=parent))
    try:
        (staging / "blobs").mkdir()
        _write_synced(staging / "manifest.json", manifest)
        for blob in selected:
            raw = graph.archive[blob]
            if len(raw) != sizes[blob] or digest(raw) != blob:
                raise ValueError(f"Captured blob differs from manifest: {blob}")
            _write_synced(staging / "blobs" / f"{blob}.pkl", raw)
        for name, raw in (extra_files or {}).items():
            if name in {"manifest.json", "blobs"} or Path(name).name != name or not name:
                raise ValueError("Extra store files must have safe unique names")
            _write_synced(staging / name, raw)
        _sync_directory(staging / "blobs")
        _sync_directory(staging)
        if checkpoint is not None:
            checkpoint("staged")
        # The single-publisher contract prevents a second writer from racing
        # this final check. The rename stays on the same filesystem.
        if destination.exists():
            raise FileExistsError(destination)
        staging.rename(destination)
        if checkpoint is not None:
            checkpoint("published")
        _sync_directory(parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def verify_published_store(destination: Path, retained: set[str],
                           *, extra_files: Mapping[str, bytes] | None = None) -> dict:
    """Check every expected blob and reject missing or extra selected files."""
    destination = Path(destination)
    manifest = json.loads((destination / "manifest.json").read_bytes())
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported manifest schema")
    sizes = {node["blob"]: node["size"] for node in manifest["nodes"]}
    selected = set(retained)
    if not set(manifest["mandatory_blobs"]) <= selected or not selected <= sizes.keys():
        raise ValueError("Selected set differs from the manifest")
    actual = {path.stem for path in (destination / "blobs").iterdir() if path.is_file()}
    if actual != selected:
        raise ValueError("Published blob inventory differs")
    for blob in selected:
        path = destination / "blobs" / f"{blob}.pkl"
        raw = path.read_bytes()
        if len(raw) != sizes[blob] or digest(raw) != blob:
            raise ValueError(f"Published blob differs: {blob}")
    for name, expected in (extra_files or {}).items():
        if (destination / name).read_bytes() != expected:
            raise ValueError(f"Published extra file differs: {name}")
    return {"status": "PASS", "blobs": len(selected), "manifest_sha256": digest(canonical(manifest))}
