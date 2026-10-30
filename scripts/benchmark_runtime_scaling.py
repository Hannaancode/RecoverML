"""Audited final-file-API thread and same-host process-replica sweeps.

Each request gets a fresh output directory. A process-replica sweep measures
single-host capacity, not distributed recovery or network scale-out.
"""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def percentile(values, q):
    values = sorted(values)
    position = (len(values) - 1) * q / 100
    lower = int(position)
    weight = position - lower
    return values[lower] * (1 - weight) + values[min(lower + 1, len(values) - 1)] * weight


def restore_one(store, output, target_ids, request_id, trial, submitted_ns):
    started_ns = time.perf_counter_ns()
    try:
        receipt = recover_requested_files(store, output / str(request_id), target_ids=target_ids,
                                          disabled=(), replay_execute=execute)
        status, error = receipt["status"], None
        hashes = receipt["target_sha256"]
        mode = receipt["mode"]
    except Exception as exc:
        status, error, hashes, mode = "FAIL", repr(exc), {}, None
    ended_ns = time.perf_counter_ns()
    return dict(trial=trial, request_id=request_id, target_ids=target_ids,
                submitted_ns=submitted_ns, started_ns=started_ns, ended_ns=ended_ns,
                service_ms=(ended_ns - started_ns) / 1e6,
                response_ms=(ended_ns - submitted_ns) / 1e6,
                status=status, error=error, target_sha256=hashes, recovery_mode=mode)


def warm(store, output, target_ids):
    return restore_one(store, output, target_ids, -1, "warmup", time.perf_counter_ns())


def expected_trials(cfg):
    for dataset, recipe in cfg["workloads"]:
        for versions in cfg["versions"]:
            for mode in cfg["modes"]:
                for axis, counts in (("threads", cfg["threads"]), ("processes", cfg["processes"])):
                    for count in counts:
                        for repeat in range(cfg["repeats"]):
                            yield dataset, recipe, versions, mode, axis, count, repeat


def run(config_path, output, smoke=False):
    cfg = json.loads(Path(config_path).read_bytes())
    if smoke:
        cfg = dict(cfg, workloads=cfg["workloads"][:1], versions=[1], modes=["root_replay", "target_files"],
                   threads=[1, 2], processes=[1, 2], requests=8, repeats=1)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "config.json", cfg)
    source_paths = [ROOT / "src/recoverml" / name for name in
                    ("core.py", "broad_workflows.py", "file_export.py", "file_recovery.py",
                     "store_publish.py", "witness.py")]
    source_paths += [Path(__file__).resolve(), Path(config_path).resolve()]
    provenance = dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      platform=platform.platform(), cpu_count=os.cpu_count(),
                      cpu_quota=(Path("/sys/fs/cgroup/cpu.max").read_text().strip()
                                 if Path("/sys/fs/cgroup/cpu.max").exists() else None),
                      source_sha256={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in source_paths},
                      started_ns=time.time_ns(),
                      scope="Final RecoverML file API; warm page cache; fresh output directory and recovery state per request",
                      process_scope="Same-host independent worker processes sharing one read-only store; no network or distributed coordination",
                      throughput_scope="all exact requests divided by burst submission-to-last-completion wall time")
    captures = {}
    trials = []
    requests_path = output / "requests.jsonl"
    trials_path = output / "trials.jsonl"
    with requests_path.open("w", encoding="utf-8") as request_log, trials_path.open("w", encoding="utf-8") as trial_log:
        for dataset, recipe in cfg["workloads"]:
            for versions in cfg["versions"]:
                key = f"{dataset}-{recipe}-v{versions}"
                graph, info = capture(dataset, recipe, versions, cfg["seed"] + versions)
                captures[key] = dict(info=info, manifest=graph.manifest())
                for mode in cfg["modes"]:
                    selected = set(graph.roots)
                    if mode == "target_files":
                        selected |= {graph.nodes[node].blob for targets in graph.targets.values() for node in targets}
                    elif mode != "root_replay":
                        raise ValueError(mode)
                    store = output / "stores" / f"{key}-{mode}"
                    expected_contract = contract({}, 0)
                    publish_store(graph, selected, store,
                                  extra_files={"capability_contract.json": expected_contract})
                    verify_published_store(store, selected,
                                           extra_files={"capability_contract.json": expected_contract})
                    captures[key].setdefault("selected", {})[mode] = sorted(selected)
                    captures[key].setdefault("store_bytes", {})[mode] = sum(p.stat().st_size for p in store.rglob("*") if p.is_file())
                    for axis, counts in (("threads", cfg["threads"]), ("processes", cfg["processes"])):
                        for count in counts:
                            for repeat in range(cfg["repeats"]):
                                trial = f"{key}-{mode}-{axis}{count}-rep{repeat}"
                                output_root = output / "scratch" / trial
                                output_root.mkdir(parents=True)
                                executor_class = ThreadPoolExecutor if axis == "threads" else ProcessPoolExecutor
                                with executor_class(max_workers=count) as pool:
                                    warm_id = graph.targets[str(versions - 1)]
                                    warmups = [pool.submit(warm, store, output_root / f"warm-{index}", warm_id)
                                               for index in range(count)]
                                    if any(task.result()["status"] != "PASS" for task in warmups):
                                        raise RuntimeError("Warm recovery failed")
                                    # Fully submit the burst before collecting results.
                                    beginning_ns = time.perf_counter_ns()
                                    futures = []
                                    for request_id in range(cfg["requests"]):
                                        version = str(request_id % versions)
                                        target_ids = graph.targets[version]
                                        submitted_ns = time.perf_counter_ns()
                                        futures.append(pool.submit(restore_one, store, output_root, target_ids,
                                                                   request_id, trial, submitted_ns))
                                    rows = [future.result() for future in futures]
                                    ending_ns = time.perf_counter_ns()
                                for row in rows:
                                    request_log.write(json.dumps(row, sort_keys=True) + "\n")
                                request_log.flush()
                                expected = {graph.nodes[node].blob for targets in graph.targets.values() for node in targets}
                                if any(row["status"] != "PASS" or
                                       set(row["target_sha256"]) - expected or
                                       any(blob != observed for blob, observed in row["target_sha256"].items())
                                       for row in rows):
                                    raise RuntimeError(f"Inexact recovery: {trial}")
                                elapsed_s = (ending_ns - beginning_ns) / 1e9
                                summary = dict(trial=trial, dataset=dataset, recipe=recipe, versions=versions,
                                               mode=mode, axis=axis, workers=count, repeat=repeat,
                                               requests=len(rows), exact=len(rows), elapsed_s=elapsed_s,
                                               throughput_rps=len(rows) / elapsed_s,
                                               service_p50_ms=percentile([r["service_ms"] for r in rows], 50),
                                               service_p99_ms=percentile([r["service_ms"] for r in rows], 99),
                                               response_p99_ms=percentile([r["response_ms"] for r in rows], 99),
                                               started_ns=beginning_ns, ended_ns=ending_ns)
                                trials.append(summary)
                                trial_log.write(json.dumps(summary, sort_keys=True) + "\n")
                                trial_log.flush()
                                print(trial, f"{len(rows)} exact", f"{summary['throughput_rps']:.1f}/s", flush=True)
                                shutil.rmtree(output_root)
                    shutil.rmtree(store)
    shutil.rmtree(output / "stores")
    shutil.rmtree(output / "scratch")
    dump(output / "captures.json", captures)
    provenance["ended_ns"] = time.time_ns()
    dump(output / "provenance.json", provenance)
    audit_result = audit(output)
    dump(output / "audit.json", audit_result)
    hashes = {path.name: digest(path.read_bytes()) for path in output.iterdir() if path.is_file()}
    dump(output / "HASHES.json", hashes)
    (output / "RUN_COMPLETE").write_text("All declared scaling trials and requests audited.\n")
    return audit_result


def audit(output):
    output = Path(output)
    hashes_path = output / "HASHES.json"
    if hashes_path.exists():
        hashes = json.loads(hashes_path.read_bytes())
        if any(digest((output / name).read_bytes()) != expected for name, expected in hashes.items()):
            raise ValueError("Evidence file hash differs")
    cfg = json.loads((output / "config.json").read_bytes())
    captures = json.loads((output / "captures.json").read_bytes())
    trials = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
    rows = [json.loads(line) for line in (output / "requests.jsonl").read_text().splitlines()]
    expected = list(expected_trials(cfg))
    if len(trials) != len(expected) or len({r["trial"] for r in trials}) != len(expected):
        raise ValueError("Trial matrix differs")
    by_trial = {}
    for row in rows:
        by_trial.setdefault(row["trial"], []).append(row)
    if len(rows) != len(expected) * cfg["requests"] or set(by_trial) != {t["trial"] for t in trials}:
        raise ValueError("Request matrix differs")
    for trial, identity in zip(trials, expected):
        dataset, recipe, versions, mode, axis, workers, repeat = identity
        if (trial["dataset"], trial["recipe"], trial["versions"], trial["mode"],
            trial["axis"], trial["workers"], trial["repeat"]) != identity:
            raise ValueError("Trial order or configuration differs")
        graph = captures[f"{dataset}-{recipe}-v{versions}"]["manifest"]
        nodes = {node["id"]: node["blob"] for node in graph["nodes"]}
        actual = by_trial[trial["trial"]]
        if {r["request_id"] for r in actual} != set(range(cfg["requests"])):
            raise ValueError("Request IDs differ")
        for row in actual:
            targets = graph["targets"][str(row["request_id"] % versions)]
            expected_hashes = {nodes[node]: nodes[node] for node in targets}
            if row["status"] != "PASS" or row["target_ids"] != targets or row["target_sha256"] != expected_hashes:
                raise ValueError("Exact target verification differs")
            if not row["submitted_ns"] <= row["started_ns"] <= row["ended_ns"] <= trial["ended_ns"]:
                raise ValueError("Request timestamp order differs")
            if abs(row["service_ms"] - (row["ended_ns"] - row["started_ns"]) / 1e6) > 1e-6:
                raise ValueError("Service latency differs")
            if abs(row["response_ms"] - (row["ended_ns"] - row["submitted_ns"]) / 1e6) > 1e-6:
                raise ValueError("Response latency differs")
        if trial["requests"] != cfg["requests"] or trial["exact"] != cfg["requests"]:
            raise ValueError("Trial request count differs")
        elapsed = (trial["ended_ns"] - trial["started_ns"]) / 1e9
        if abs(trial["throughput_rps"] - cfg["requests"] / elapsed) > 1e-5:
            raise ValueError("Throughput differs")
        for field, values, q in (("service_p50_ms", [r["service_ms"] for r in actual], 50),
                                 ("service_p99_ms", [r["service_ms"] for r in actual], 99),
                                 ("response_p99_ms", [r["response_ms"] for r in actual], 99)):
            if abs(trial[field] - percentile(values, q)) > 1e-6:
                raise ValueError("Percentile differs")
    return dict(status="PASS", trials=len(trials), requests=len(rows), exact=len(rows),
                workloads=len(cfg["workloads"]), version_scales=len(cfg["versions"]),
                modes=len(cfg["modes"]), axes=["threads", "same_host_processes"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/runtime_scaling_oct30.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.output) if args.audit_only else run(args.config, args.output, args.smoke), indent=2))
