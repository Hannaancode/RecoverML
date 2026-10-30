"""One independent stateless recovery replica in a synchronized runner sweep."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

from recoverml.broad_workflows import capture, execute
from recoverml.capability_retention import contract
from recoverml.core import digest
from recoverml.file_recovery import recover_requested_files
from recoverml.store_publish import publish_store, verify_published_store


ROOT = Path(__file__).resolve().parents[1]
SEED = 20261046
VERSIONS = 16


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def wait_until(epoch_ns):
    while True:
        remaining = (epoch_ns - time.time_ns()) / 1e9
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1))


def run(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    graph, info = capture("digits", "pca_neighbors", VERSIONS, SEED)
    selected = set(graph.roots)
    store = out / "store"
    expected_contract = contract({}, 0)
    publish_store(graph, selected, store, extra_files={"capability_contract.json": expected_contract})
    verify_published_store(store, selected, extra_files={"capability_contract.json": expected_contract})
    warm_output = out / "warm"
    warm = recover_requested_files(store, warm_output,
                                   target_ids=graph.targets[str(VERSIONS - 1)],
                                   disabled=(), replay_execute=execute)
    if warm["status"] != "PASS":
        raise RuntimeError("Replica warmup failed")
    config = dict(scenario=args.scenario, replica=args.replica,
                  start_epoch_ns=args.start_epoch_ns, interval_s=args.interval_s,
                  requests=args.requests, repeats=args.repeats,
                  dataset="digits", recipe="pca_neighbors", versions=VERSIONS,
                  seed=SEED, selected=sorted(selected), store_bytes=sum(p.stat().st_size for p in store.rglob("*") if p.is_file()),
                  manifest=graph.manifest())
    dump(out / "config.json", config)
    provenance = dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      platform=platform.platform(), cpu_count=os.cpu_count(),
                      cpu_quota=(Path("/sys/fs/cgroup/cpu.max").read_text().strip()
                                 if Path("/sys/fs/cgroup/cpu.max").exists() else None),
                      cpuinfo=(Path("/proc/cpuinfo").read_text().split("\n\n")[0]
                               if Path("/proc/cpuinfo").exists() else "unavailable"),
                      source_sha256={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
                                     (Path(__file__).resolve(), ROOT / "src/recoverml/file_recovery.py",
                                      ROOT / "src/recoverml/store_publish.py",
                                      ROOT / "src/recoverml/broad_workflows.py")})
    dump(out / "provenance.json", provenance)
    summaries = []
    with (out / "requests.jsonl").open("w", encoding="utf-8") as stream:
        for repeat in range(args.repeats):
            scheduled_ns = args.start_epoch_ns + repeat * args.interval_s * 1_000_000_000
            wait_until(scheduled_ns)
            began_ns = time.time_ns()
            observed = []
            for request_id in range(args.requests):
                target_ids = graph.targets[str(request_id % VERSIONS)]
                started_ns = time.time_ns()
                output = out / "scratch" / f"rep{repeat}-request{request_id}"
                receipt = recover_requested_files(store, output, target_ids=target_ids,
                                                  disabled=(), replay_execute=execute)
                ended_ns = time.time_ns()
                expected_hashes = {graph.nodes[node].blob: graph.nodes[node].blob for node in target_ids}
                exact = receipt["status"] == "PASS" and receipt["target_sha256"] == expected_hashes
                row = dict(scenario=args.scenario, replica=args.replica, repeat=repeat,
                           request_id=request_id, target_ids=target_ids, target_sha256=receipt["target_sha256"],
                           started_ns=started_ns, ended_ns=ended_ns, exact=exact,
                           service_ms=(ended_ns - started_ns) / 1e6)
                stream.write(json.dumps(row, sort_keys=True) + "\n")
                observed.append(row)
                if not exact:
                    raise RuntimeError("Replica target hash differs")
            ended_ns = time.time_ns()
            stream.flush()
            summary = dict(scenario=args.scenario, replica=args.replica, repeat=repeat,
                           scheduled_ns=scheduled_ns, began_ns=began_ns, ended_ns=ended_ns,
                           requests=len(observed), exact=sum(row["exact"] for row in observed),
                           throughput_rps=len(observed) / ((ended_ns - began_ns) / 1e9))
            summaries.append(summary)
            print(summary, flush=True)
            shutil.rmtree(out / "scratch")
    dump(out / "summary.json", summaries)
    shutil.rmtree(store)
    shutil.rmtree(warm_output)
    hashes = {p.name: digest(p.read_bytes()) for p in out.iterdir() if p.is_file()}
    dump(out / "HASHES.json", hashes)
    (out / "RUN_COMPLETE").write_text("Replica complete.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=int, choices=(1, 2, 4), required=True)
    parser.add_argument("--replica", type=int, required=True)
    parser.add_argument("--start-epoch-ns", type=int, required=True)
    parser.add_argument("--requests", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--interval-s", type=int, default=90)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.replica < args.scenario:
        raise ValueError("Replica index is outside its declared scenario")
    run(args)
