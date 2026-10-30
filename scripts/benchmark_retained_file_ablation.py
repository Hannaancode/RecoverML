"""Same-store, same-request ablation of retained-file recovery overhead.

The three arms isolate certification/setup and retained-object conversion.
They are internal RecoverML paths, not comparisons with another system.
"""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import time

from recoverml.broad_workflows import capture
from recoverml.capability_retention import contract, restricted
from recoverml.core import Graph, digest, pack
from recoverml.file_export import export_retained_targets
from recoverml.file_recovery import recover_requested_files
from recoverml.store_publish import publish_store, verify_published_store
from recoverml.witness import WitnessRestorer


ROOT = Path(__file__).resolve().parents[1]
ARMS = ("direct_export", "certified_export", "certified_deserialize")


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def percentile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low = int(position)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[min(low + 1, len(ordered) - 1)] * weight


def run_arm(arm, store, output, target_ids):
    if arm == "direct_export":
        receipt = recover_requested_files(store, output, target_ids=target_ids)
        if receipt["mode"] != "retained_file_export":
            raise ValueError("The direct arm did not export retained files")
        return receipt["target_sha256"]

    graph = Graph.read(store / "manifest.json")
    retained_contract = json.loads((store / "capability_contract.json").read_bytes())
    view = restricted(graph, retained_contract["capabilities"], ())
    view.targets = {"request": list(target_ids)}
    restorer = WitnessRestorer(view, store)
    if arm not in ("certified_export", "certified_deserialize"):
        raise ValueError("Unknown arm")
    receipt = export_retained_targets(store, output, target_ids=target_ids)
    if receipt is None:
        raise ValueError("The certified arm could not export retained files")
    if arm == "certified_export":
        return receipt["target_sha256"]
    # This is deliberately additive: the output is first exported exactly as
    # in the preceding arm, then each object is loaded and repacked in memory.
    # It measures conversion plus the source reread; it is not a pure CPU cost.
    for target in target_ids:
        expected = graph.nodes[target].blob
        data = pack(restorer.get(target))
        if digest(data) != expected:
            raise ValueError("Deserialized target did not roundtrip exactly")
        destination = output / (expected + ".pkl")
        if destination.read_bytes() != data:
            raise ValueError("Repacked object differed from the exported target file")
    return receipt["target_sha256"]


def protocol(config, smoke):
    value = json.loads(Path(config).read_bytes())
    required = {"workloads", "versions", "requests", "repeats", "seed"}
    if set(value) != required or value["requests"] <= 0 or value["repeats"] <= 0:
        raise ValueError("Ablation protocol differs")
    if smoke:
        value = dict(value, workloads=value["workloads"][:1], versions=[1],
                     requests=4, repeats=1)
    return value


def run(config, output, *, smoke=False):
    cfg = protocol(config, smoke)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "config.json", cfg)
    sources = [ROOT / "src/recoverml" / name for name in
               ("broad_workflows.py", "core.py", "file_export.py", "file_recovery.py",
                "witness.py", "store_publish.py", "capability_retention.py")]
    sources.extend((Path(__file__).resolve(), Path(config).resolve()))
    provenance = dict(source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                              text=True).strip(),
                      platform=platform.platform(), cpu_count=os.cpu_count(),
                      source_sha256={str(path.relative_to(ROOT)): digest(path.read_bytes())
                                     for path in sources},
                      comparison="Three internal paths, same physically retained files, targets and fresh output per request; third arm adds object conversion and source reread after identical export",
                      cache="Warmed once per arm and case, then Latin-square arm order; OS caches not flushed")
    write_json(output / "provenance.json", provenance)
    captures = {}
    summaries = []
    with (output / "requests.jsonl").open("w", encoding="utf-8") as stream:
        for dataset, recipe in cfg["workloads"]:
            for versions in cfg["versions"]:
                case = f"{dataset}-{recipe}-v{versions}"
                graph, info = capture(dataset, recipe, versions, cfg["seed"] + versions)
                selected = set(graph.roots) | {graph.nodes[node].blob for targets in graph.targets.values()
                                               for node in targets}
                store = output / "stores" / case
                expected_contract = contract({}, 0)
                publish_store(graph, selected, store,
                              extra_files={"capability_contract.json": expected_contract})
                verify_published_store(store, selected,
                                       extra_files={"capability_contract.json": expected_contract})
                captures[case] = dict(info=info, manifest=graph.manifest(), selected=sorted(selected),
                                      store_bytes=sum(path.stat().st_size for path in store.rglob("*")
                                                      if path.is_file()))
                for arm in ARMS:
                    warm_output = output / "scratch" / case / ("warm-" + arm)
                    hashes = run_arm(arm, store, warm_output, graph.targets[str(versions - 1)])
                    expected = {graph.nodes[node].blob: graph.nodes[node].blob
                                for node in graph.targets[str(versions - 1)]}
                    if hashes != expected:
                        raise ValueError("Warmup target differs")
                shutil.rmtree(output / "scratch" / case)
                for repeat in range(cfg["repeats"]):
                    observed = defaultdict(list)
                    for request_id in range(cfg["requests"]):
                        target_ids = graph.targets[str(request_id % versions)]
                        expected = {graph.nodes[node].blob: graph.nodes[node].blob for node in target_ids}
                        for offset in range(len(ARMS)):
                            arm = ARMS[(repeat + request_id + offset) % len(ARMS)]
                            destination = output / "scratch" / case / f"repeat{repeat}-request{request_id}-{arm}"
                            start_ns = time.perf_counter_ns()
                            hashes = run_arm(arm, store, destination, target_ids)
                            end_ns = time.perf_counter_ns()
                            if hashes != expected:
                                raise ValueError("Ablation request target differs")
                            row = dict(case=case, dataset=dataset, recipe=recipe, versions=versions,
                                       repeat=repeat, request_id=request_id, arm=arm, target_ids=target_ids,
                                       target_sha256=hashes, start_ns=start_ns, end_ns=end_ns,
                                       service_ms=(end_ns - start_ns) / 1e6, exact=True)
                            stream.write(json.dumps(row, sort_keys=True) + "\n")
                            observed[arm].append(row["service_ms"])
                    stream.flush()
                    for arm in ARMS:
                        timings = observed[arm]
                        summary = dict(case=case, dataset=dataset, recipe=recipe, versions=versions,
                                       repeat=repeat, arm=arm, requests=len(timings), exact=len(timings),
                                       median_ms=statistics.median(timings), p99_ms=percentile(timings, 99))
                        summaries.append(summary)
                        print(case, repeat, arm, f"{summary['median_ms']:.3f} ms", flush=True)
                    shutil.rmtree(output / "scratch" / case)
                shutil.rmtree(store)
    shutil.rmtree(output / "stores")
    shutil.rmtree(output / "scratch")
    write_json(output / "captures.json", captures)
    write_json(output / "summary.json", summaries)
    result = audit(output)
    write_json(output / "audit.json", result)
    hashes = {path.name: digest(path.read_bytes()) for path in output.iterdir() if path.is_file()}
    write_json(output / "HASHES.json", hashes)
    (output / "RUN_COMPLETE").write_text("All same-store ablation requests audited.\n")
    return result


def audit(output):
    output = Path(output)
    if (output / "HASHES.json").is_file():
        hashes = json.loads((output / "HASHES.json").read_bytes())
        if any(digest((output / name).read_bytes()) != sha for name, sha in hashes.items()):
            raise ValueError("Ablation evidence hash differs")
    cfg = json.loads((output / "config.json").read_bytes())
    captures = json.loads((output / "captures.json").read_bytes())
    summaries = json.loads((output / "summary.json").read_bytes())
    requests = [json.loads(line) for line in (output / "requests.jsonl").read_text().splitlines()]
    expected = [(dataset, recipe, versions, repeat, arm)
                for dataset, recipe in cfg["workloads"] for versions in cfg["versions"]
                for repeat in range(cfg["repeats"]) for arm in ARMS]
    if len(summaries) != len(expected) or len(requests) != len(expected) * cfg["requests"]:
        raise ValueError("Ablation matrix differs")
    expected_sequence = [(f"{dataset}-{recipe}-v{versions}", repeat, request_id,
                          ARMS[(repeat + request_id + offset) % len(ARMS)])
                         for dataset, recipe in cfg["workloads"] for versions in cfg["versions"]
                         for repeat in range(cfg["repeats"]) for request_id in range(cfg["requests"])
                         for offset in range(len(ARMS))]
    actual_sequence = [(row["case"], row["repeat"], row["request_id"], row["arm"])
                       for row in requests]
    if actual_sequence != expected_sequence:
        raise ValueError("Ablation paired requests or balanced arm order differs")
    by_group = defaultdict(list)
    for row in requests:
        key = (row["dataset"], row["recipe"], row["versions"], row["repeat"], row["arm"])
        by_group[key].append(row)
        case = row["case"]
        if case != f"{row['dataset']}-{row['recipe']}-v{row['versions']}" or case not in captures:
            raise ValueError("Ablation case differs")
        graph = captures[case]["manifest"]
        nodes = {node["id"]: node["blob"] for node in graph["nodes"]}
        targets = graph["targets"][str(row["request_id"] % row["versions"])]
        expected_hashes = {nodes[node]: nodes[node] for node in targets}
        if (row["target_ids"] != targets or row["target_sha256"] != expected_hashes or
            row["exact"] is not True or row["end_ns"] < row["start_ns"] or
            abs(row["service_ms"] - (row["end_ns"] - row["start_ns"]) / 1e6) > 1e-6):
            raise ValueError("Ablation exactness or timing differs")
    if set(by_group) != set(expected):
        raise ValueError("Ablation group set differs")
    for summary, key in zip(summaries, expected):
        actual = by_group[key]
        if ({row["request_id"] for row in actual} != set(range(cfg["requests"])) or
            (summary["dataset"], summary["recipe"], summary["versions"],
             summary["repeat"], summary["arm"]) != key or
            summary["requests"] != cfg["requests"] or summary["exact"] != cfg["requests"] or
            abs(summary["median_ms"] - statistics.median(row["service_ms"] for row in actual)) > 1e-6 or
            abs(summary["p99_ms"] - percentile([row["service_ms"] for row in actual], 99)) > 1e-6):
            raise ValueError("Ablation summary differs")
    return dict(status="PASS", trials=len(summaries), requests=len(requests), exact=len(requests),
                workloads=len(cfg["workloads"]), version_scales=len(cfg["versions"]),
                arms=list(ARMS), store_comparability="same selected physical files within each case")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/retained_file_ablation_oct30.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    result = audit(args.output) if args.audit_only else run(args.config, args.output, smoke=args.smoke)
    print(json.dumps(result, indent=2))
