"""Review the saved exact-solver study and time existing storage formats."""
import collections
import csv
import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tarfile
import time
import zipfile

from recoverml.core import Graph, Node, digest
from recoverml.delta_store import DeltaRepresentation, open_store
from recoverml.encoded_store import Representation
from recoverml.solid_store import SolidRepresentation

ROOT = Path(__file__).resolve().parents[1]
STORES = ("flat", "delta", "joint")
HISTORIES = (("wine", "robust_forest", 16), ("digits", "pca_neighbors", 16))


def read_capture(dataset, recipe, versions):
    source = f"results/research/recovery_census_oct26/artifacts/recovery-census-{dataset}-{recipe}.zip"
    prefix = f"captures/{dataset}-{recipe}-v{versions}/"
    path = ROOT / source
    with zipfile.ZipFile(path) as outer, tarfile.open(
        fileobj=io.BytesIO(outer.read("census/captures.tar.gz")), mode="r:gz"
    ) as captures:
        raw_manifest = captures.extractfile(prefix + "manifest.json").read()
        manifest = json.loads(raw_manifest)
        graph = Graph(env=manifest["environment"])
        graph.nodes = {row["id"]: Node(**row) for row in manifest["nodes"]}
        graph.roots = set(manifest["mandatory_blobs"])
        graph.targets = manifest["targets"]
        for blob, size in graph.sizes().items():
            payload = captures.extractfile(prefix + f"blobs/{blob}.pkl").read()
            if len(payload) != size or digest(payload) != blob:
                raise ValueError("Archived payload differs from manifest")
            graph.archive[blob] = payload
    return graph, {
        "source": source,
        "zip_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "manifest_sha256": digest(raw_manifest),
    }


def peak_rss():
    if os.name != "nt":
        import resource
        measured = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return measured if sys.platform == "darwin" else measured * 1024
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "peak", "working", "peak_paged", "paged", "peak_nonpaged",
                "nonpaged", "pagefile", "peak_pagefile")
        ]
    query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    query.restype = wintypes.BOOL
    process = ctypes.WinDLL("kernel32").GetCurrentProcess
    process.restype = wintypes.HANDLE
    info = Counters()
    info.cb = ctypes.sizeof(info)
    if not query(process(), ctypes.byref(info), info.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return info.peak


def build(dataset, recipe, versions, storage, path):
    graph, provenance = read_capture(dataset, recipe, versions)
    selected = graph.candidates
    baseline = peak_rss()
    begin = time.perf_counter_ns()
    if storage == "flat":
        repr_ = Representation(graph)
        selection = selected
    elif storage == "delta":
        repr_ = DeltaRepresentation(graph)
        # Keep bases as full files and use the declared delta for other eligible blobs.
        bases = set(repr_.bases.values())
        selection = {
            repr_.delta_tokens[b] if b in repr_.delta_tokens and b not in bases
            else repr_.full_tokens[b] for b in selected
        }
    else:
        repr_ = SolidRepresentation(graph)
        repr_.files(selected, {}, 0)
        selection = selected
    encoded_at = time.perf_counter_ns()
    size = repr_.write(selection, {}, 0, path)
    end = time.perf_counter_ns()
    peak = peak_rss()
    loaded = open_store(path)
    if loaded.retained != selected or any(loaded.load(b) != graph.archive[b] for b in selected):
        raise ValueError("A storage format changed the selected canonical bytes")
    return dict(**provenance, stored_bytes=size, retained_blobs=len(selected),
                canonical_bytes=sum(graph.sizes().values()),
                delta_files=sum(t in repr_.delta_tokens.values() for t in selection) if storage == "delta" else 0,
                encode_ms=(encoded_at-begin)/1e6, create_ms=(end-begin)/1e6,
                peak_bytes=peak, peak_before_bytes=baseline)


def access(path, output, selection):
    baseline = peak_rss()
    begin = time.perf_counter_ns()
    store = open_store(path)
    opened = time.perf_counter_ns()
    model = store.graph.targets[str(max(map(int, store.graph.targets)))][0]
    ids = [model] if selection == "single" else sorted(store.protected)
    expected = {store.graph.nodes[n].blob for n in ids}
    receipt = store.recover(output, target_ids=ids)
    end = time.perf_counter_ns()
    peak = peak_rss()
    files = {f.stem: digest(f.read_bytes()) for f in output.glob("*.pkl")}
    if files != {b: b for b in expected} or receipt["target_sha256"] != files or receipt["operations"]:
        raise ValueError("Retained-file read differs from the archived target hashes")
    return dict(open_ms=(opened-begin)/1e6, access_ms=(end-opened)/1e6,
                total_ms=(end-begin)/1e6, exact_hashes=len(files),
                target_hashes=files, peak_bytes=peak, peak_before_bytes=baseline)


def solver_evidence():
    source = ROOT / "results/research/paper_oct14/scaling/summary.csv"
    by_case = collections.defaultdict(list)
    with source.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["status"] != "ok" or row["analytic_match"] != "True":
                raise ValueError("Earlier solver sweep contains an uncertified result")
            by_case[(int(row["groups"]), int(row["k"]), row["policy"])].append(row)
    if sum(map(len, by_case.values())) != 60 or len(by_case) != 12:
        raise ValueError("Earlier solver grid is incomplete")
    return [{
        "groups": groups, "k": k, "policy": policy, "trials": len(rows),
        "scenarios": int(rows[0]["scenarios"]),
        "median_ms": 1000*statistics.median(float(row["elapsed_s"]) for row in rows),
        "retained_bytes": int(rows[0]["retained_bytes"]),
        "expanded_variables": int(rows[0]["variables"]) if rows[0]["variables"] else None,
        "master_variables": int(rows[0]["master_variables"]) if rows[0]["master_variables"] else None,
    } for (groups, k, policy), rows in sorted(by_case.items())]


def run(out):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    def child(*args):
        return json.loads(subprocess.check_output(
            [sys.executable, str(Path(__file__).resolve()), *map(str,args)], text=True, timeout=90))
    with (out/"runs.jsonl").open("x", encoding="utf8") as ledger:
        for dataset, recipe, versions in HISTORIES:
            for repeat in range(3):
                order = STORES[repeat:] + STORES[:repeat]
                for storage in order:
                    base = out / f"{dataset}-{recipe}-{repeat}-{storage}"
                    row = child("build", dataset, recipe, versions, storage, base/"store")
                    identity = dict(dataset=dataset, recipe=recipe, versions=versions, repeat=repeat, storage=storage)
                    ledger.write(json.dumps(dict(**identity, phase="build", **row))+"\n")
                    ledger.flush()
                    for selection in ("single","all"):
                        row = child("access", base/"store", base/selection, selection)
                        ledger.write(json.dumps(dict(**identity, phase=selection, **row))+"\n")
                        ledger.flush()
                    print(dataset,recipe,repeat,storage,flush=True)
    report = dict(host=platform.platform(), cpu=platform.processor(), python=sys.version,
                  source_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                  benchmark_sha256=digest(Path(__file__).read_bytes()),
                  m4_saved_solver_rows=solver_evidence())
    (out/"provenance.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "run":
        run(Path(args[0]))
    elif mode == "build":
        dataset, recipe, versions, format_, path = args
        print(json.dumps(build(dataset, recipe, int(versions), format_, Path(path))))
    else:
        path, output, selection = args
        print(json.dumps(access(Path(path), Path(output), selection)))
