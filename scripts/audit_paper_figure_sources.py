#!/usr/bin/env python3
"""Audit the measurements behind the revised paper figures.

This is a read-only build gate. It recomputes plotted numbers from saved
lower-level records. It does not claim that missing original payload archives
can be recovered from ledgers, or that an architecture drawing is experimental
evidence.
"""

from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import tarfile
import zipfile

from recoverml.capability_retention import contract, retained_bytes
from recoverml.core import Graph
from recoverml.eyeai_workflow import capabilities_for, target_view


ROOT = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, label):
    check(math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-12),
          f"{label}: {actual} != {expected}")


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def gz_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def shared_storage():
    base = ROOT / "results/research/strong_baseline_cloud_oct16"
    histories = 0
    raw_records = 0
    for seed in (20261016, 20261017, 20261018):
        folder = base / f"seed{seed}/shared"
        summary = csv_rows(folder / "summary.csv")
        plans = gz_json(folder / "planner_records.json.gz")
        by_key = defaultdict(list)
        for plan in plans:
            by_key[(plan["history"], plan["method"])].append(plan)
        check(len(plans) == 324 and len(summary) == 108, f"shared seed {seed}: incomplete grid")
        check(len(by_key) == len(summary), f"shared seed {seed}: plan identity grid differs")
        for row in summary:
            key = row["history"], row["method"]
            reps = by_key[key]
            check(len(reps) == 3 and {r["repetition"] for r in reps} == {0, 1, 2},
                  f"{key}: incomplete planner repetitions")
            check(len({r["retained_bytes"] for r in reps}) == 1,
                  f"{key}: retained bytes vary across planner repetitions")
            check(int(row["retained_bytes"]) == reps[0]["retained_bytes"],
                  f"{key}: summary bytes differ from planner records")
            close(row["planning_median_s"], statistics.median(r["planning_s"] for r in reps),
                  f"{key}: planning median")
        methods = defaultdict(set)
        for row in summary:
            methods[row["history"]].add(row["method"])
        check(len(methods) == 12 and all({"RecoverML_exact", "robust_local"} <= x for x in methods.values()),
              f"shared seed {seed}: plotted pairs missing")
        histories += len(methods)
        raw_records += len(plans)
    check(histories == 36, "shared storage: plotted history count differs")
    return {"histories": histories, "planner_records_checked": raw_records,
            "source": "per-repetition planner_records.json.gz reconciled to summary.csv"}


def planner_timing():
    folder = ROOT / "results/research/strong_baseline_cloud_oct16/seed20261016/dag_timing"
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))["results"]
    calls = gz_json(folder / "planner_calls.json.gz")
    grouped = defaultdict(list)
    for row in calls:
        grouped[(row["case"], row["method"])].append(row)
    check(len(report) == 48 and len(calls) == 720 and len(grouped) == 144,
          "planner timing: incomplete trial grid")
    check(sum(bool(row["dag_eligible"]) for row in report) == 36,
          "planner timing: eligibility count differs")
    methods = ("RecoverML_auto", "robust_local", "scenario_exact")
    for row in report:
        medians = {}
        for method in methods:
            reps = grouped[(row["case"], method)]
            check(len(reps) == 5 and {r["repetition"] for r in reps} == set(range(5)),
                  f"{row['case']}/{method}: incomplete planner calls")
            medians[method] = statistics.median(r["planning_s"] for r in reps)
            close(row["median_s"][method], medians[method], f"{row['case']}/{method}: median")
        close(row["speedup_vs_local"], medians["robust_local"] / medians["RecoverML_auto"],
              f"{row['case']}: local speedup")
        close(row["speedup_vs_scenario"], medians["scenario_exact"] / medians["RecoverML_auto"],
              f"{row['case']}: scenario speedup")
    return {"cases": len(report), "planner_calls_checked": len(calls),
            "source": "five raw planner calls per method/case reconciled to report.json"}


def native_recovery():
    base = ROOT / "results/research/native_frontier_cloud_oct16/v4"
    raw = []
    for seed in (20261016, 20261017, 20261018):
        path = base / f"seed{seed}/native_paired/raw_recovery.jsonl"
        raw.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    counts = Counter((row["history"], row["method"]) for row in raw)
    check(len(raw) == 216 and len(counts) == 72 and set(counts.values()) == {3},
          "native recovery: raw paired trial grid differs")
    for history in {row["history"] for row in raw}:
        check({method for case, method in counts if case == history} ==
              {"RecoverML_native", "DVC_native_batch"}, f"{history}: native method pair differs")
    return {"histories": 36, "raw_trials_checked": len(raw),
            "source": "raw_recovery.jsonl, three trials per method/history"}


def retinal_storage():
    folder = ROOT / "results/research/eyeai_complete_oct15"
    rows = csv_rows(folder / "summary.csv")
    stores = gz_json(folder / "store_index.json.gz")
    plans = gz_json(folder / "planner_records.json.gz")
    by_id = {row["condition_id"]: row for row in rows}
    by_store = {row["condition_id"]: row for row in stores}
    by_plan = {row["condition_id"]: row for row in plans}
    check(len(rows) == len(stores) == len(plans) == 540 and
          set(by_id) == set(by_store) == set(by_plan), "retinal storage: condition grid differs")
    capture_graphs = {}
    plotted = 0
    for condition, row in by_id.items():
        capture = row["capture_id"]
        if capture not in capture_graphs:
            capture_graphs[capture] = Graph.read(folder / "captures" / capture / "manifest.json")
        graph = target_view(capture_graphs[capture], row["target_mode"])
        caps, k = capabilities_for(graph, row["availability"])
        store, plan = by_store[condition], by_plan[condition]
        check(store["manifest"] == graph.manifest() and store["capabilities"] == caps and
              store["k"] == k, f"{condition}: captured graph/contract differs")
        selected = set(store["selected"])
        check(selected == set(plan["selected"]) and len(selected) == len(store["selected"]),
              f"{condition}: store and planner memberships differ")
        check(retained_bytes(graph, selected, caps, k) == int(row["retained_bytes"]),
              f"{condition}: summary bytes differ from captured graph and store membership")
        if row["policy"] in {"RecoverML_exact", "DVC_target_snapshots"}:
            plotted += 1
    check(plotted == 216 and len(capture_graphs) == 18,
          "retinal storage: plotted pair or capture grid differs")
    return {"conditions_checked": len(rows), "plotted_rows": plotted,
            "capture_manifests": len(capture_graphs),
            "source": "capture manifests and stored physical selections recompute byte accounting"}


def letter_storage():
    folder = ROOT / "results/research/gigabyte_letter_oct16"
    rows = csv_rows(folder / "summary.csv")
    plans = {(row["scope"], row["policy"]): row for row in
             json.loads((folder / "planner_records.json").read_text(encoding="utf-8"))}
    inventory = json.loads((folder / "blob_inventory.json").read_text(encoding="utf-8"))
    graph = Graph.read(folder / "manifest.json")
    headline = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))["scopes"]
    target_blobs = {graph.nodes[node].blob for targets in graph.targets.values() for node in targets}
    snapshots = graph.roots | target_blobs
    check(len(rows) == len(plans) == 10 and set(inventory) == graph.candidates,
          "Letter: incomplete plan/summary/blob inventory grid")
    for row in rows:
        scope, policy = row["scope"], row["policy"]
        plan = plans[(scope, policy)]
        selected, caps = set(plan["selected"]), plan["capabilities"]
        overhead = graph.metadata_bytes() + len(contract(caps, 1))
        measured = overhead + sum(inventory[blob]["bytes"] for blob in selected)
        compressed = overhead + sum(inventory[blob]["gzip_bytes"] for blob in selected)
        baseline = overhead + sum(inventory[blob]["bytes"] for blob in snapshots)
        gzip_baseline = overhead + sum(inventory[blob]["gzip_bytes"] for blob in snapshots)
        check(int(row["retained_bytes"]) == plan["retained_bytes"] == measured,
              f"Letter {scope}/{policy}: retained bytes differ")
        check(int(row["gzip_retained_bytes"]) == plan["compressed_retained_bytes"] == compressed,
              f"Letter {scope}/{policy}: gzip bytes differ")
        check(int(row["baseline_bytes"]) == plan["budget_bytes"] == baseline and
              int(row["gzip_baseline_bytes"]) == gzip_baseline,
              f"Letter {scope}/{policy}: baseline bytes differ")
        if policy == "RecoverML_exact":
            expected = headline[scope]
            for name, value in (("snapshot_bytes", baseline), ("gzip_snapshot_bytes", gzip_baseline),
                                ("exact_bytes", measured), ("gzip_exact_bytes", compressed)):
                check(expected[name] == value, f"Letter {scope}: analysis {name} differs")
    original = folder / "selected_frontier.tar.gz"
    membership = json.loads((folder / "store_membership.json").read_text(encoding="utf-8"))
    receipt = json.loads((folder / "frontier_recovery_receipt.json").read_text(encoding="utf-8"))
    reconstructed = folder / "recovered_frontier_payloads.tar.gz"
    preflight = ROOT / receipt["source_preflight"]
    for path, digest in ((reconstructed, receipt["replacement_sha256"]),
                         (preflight, receipt["source_preflight_sha256"])):
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        check(actual == digest, f"Letter: {path.name} hash differs from recovery receipt")
    frontier = plans[("preprocessing", "RecoverML_exact")]
    expected_members = {"manifest.json", "capability_contract.json"} | {
        f"blobs/{blob}.pkl" for blob in frontier["selected"]}
    with tarfile.open(reconstructed, "r:gz") as archive:
        members = archive.getnames()
        check(set(members) == expected_members and len(members) == len(expected_members),
              "Letter: reconstructed frontier archive membership differs")
        check(json.loads(archive.extractfile("manifest.json").read()) == graph.manifest(),
              "Letter: reconstructed manifest differs")
        check(archive.extractfile("capability_contract.json").read() == contract(frontier["capabilities"], 1),
              "Letter: reconstructed failure contract differs")
        payload_bytes = 0
        for blob in frontier["selected"]:
            data = archive.extractfile(f"blobs/{blob}.pkl").read()
            check(hashlib.sha256(data).hexdigest() == blob and len(data) == inventory[blob]["bytes"],
                  f"Letter: reconstructed payload differs: {blob}")
            payload_bytes += len(data)
    check(payload_bytes == receipt["payload_bytes"], "Letter: reconstructed payload byte sum differs")
    if original.exists():
        with original.open("rb") as stream:
            original_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        check(original_sha == membership["frontier_archive_sha256"],
              "Letter: original frontier archive hash differs")
        with tarfile.open(original, "r:gz") as archive:
            check(set(archive.getnames()) == expected_members and len(archive.getnames()) == len(expected_members),
                  "Letter: original frontier archive membership differs")
            for name in expected_members:
                original_data = archive.extractfile(name).read()
                with tarfile.open(reconstructed, "r:gz") as recovered:
                    check(original_data == recovered.extractfile(name).read(),
                          f"Letter: original frontier member differs: {name}")
    return {"plotted_scopes": 2, "plan_rows_checked": len(rows),
            "original_archive_present": original.exists(),
            "recovered_frontier_payloads_verified": len(frontier["selected"]),
            "source": "manifest, selected-set ledger, per-blob byte sizes and hash-verified reconstructed frontier payloads",
            "limit": None if original.exists() else
            "Original selected_frontier.tar.gz is absent; original archive bytes cannot be independently rechecked. Reconstructed payload bytes match saved hashes and sizes"}


def runtime_scaling():
    path = ROOT / "results/research/runtime_scaling_oct30/evidence.zip"
    with zipfile.ZipFile(path) as archive:
        raw = archive.read("runtime_scaling_full/trials.jsonl").decode("utf-8")
    trials = [json.loads(line) for line in raw.splitlines()]
    counts = Counter((row["dataset"], row["versions"], row["mode"], row["axis"], row["workers"])
                     for row in trials)
    check(len(trials) == 252 and len(counts) == 84 and set(counts.values()) == {3},
          "runtime scaling: raw trial grid differs")
    for row in trials:
        check(row["throughput_rps"] > 0 and row["service_p99_ms"] > 0,
              "runtime scaling: invalid raw metric")
    return {"raw_trials_checked": len(trials), "conditions": len(counts),
            "source": "archived GitHub Actions raw trials.jsonl"}


def main():
    results = {
        "shared_storage": shared_storage(),
        "planner_timing": planner_timing(),
        "native_recovery": native_recovery(),
        "retinal_storage": retinal_storage(),
        "letter_storage": letter_storage(),
        "runtime_scaling": runtime_scaling(),
        "methodology": {"source": "author-supplied architecture diagram, redrawn as vector art",
                        "classification": "illustration, not a measured figure"},
    }
    print(json.dumps({"status": "PASS", "figures": results}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
