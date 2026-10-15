"""Frozen nonuniform-cost/frequency/eligibility sensitivity of baseline decisions.

Read metadata only from the supplied capture archive. No pickle artifact is
loaded and no historical operation or model is executed. The pinned original
HYPPO ranking functions are executed through the explicitly declared adapter.
"""
import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tarfile

from recoverml.capability_retention import retained_bytes, restricted
from recoverml.core import Graph, Node
from recoverml.helix_materializer import select as helix
from recoverml.published_materializers import REVISION, SOURCE_SHA256, adapt, load_source
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scopes(graph, scope):
    result = {}
    for node in graph.nodes.values():
        if not node.replayable:
            continue
        if node.op == "scientific_split":
            result[node.id] = "split_membership"
        elif node.op in ("scientific_fit_transformer", "scientific_transform", "scientific_union"):
            result[node.id] = "preprocess:" + node.params["estimator"]
        elif scope == "broad" and node.op == "scientific_train":
            result[node.id] = "model_training"
        elif scope == "broad" and node.op == "scientific_predict":
            result[node.id] = "prediction"
    return result


def version_ancestry(graph):
    dependencies = {b: set() for b in graph.candidates}
    for node in graph.nodes.values():
        dependencies[node.blob] |= {graph.nodes[d].blob for d in node.deps}
    answer = []
    for targets in graph.targets.values():
        todo = [graph.nodes[t].blob for t in targets]
        seen = set()
        while todo:
            blob = todo.pop()
            if blob in seen:
                continue
            seen.add(blob)
            todo.extend(dependencies[blob] - seen)
        answer.append(seen)
    return answer


def frozen_protocol(path):
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    relative = path.resolve().relative_to(root)
    committed = subprocess.check_output(["git", "show", "HEAD:" + relative.as_posix()])
    if committed != path.read_bytes():
        raise ValueError("Commit the exact protocol before evaluating it")
    return subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(relative)], text=True).strip()


def run(captures_path, protocol_path, output, hyppo_cache):
    protocol_commit = frozen_protocol(protocol_path)
    config = json.loads(protocol_path.read_text())
    if output.exists():
        raise ValueError("Choose a new output directory to preserve existing evidence")
    expected_histories = {f"{w}-{s}" for w in config["workflows"] for s in config["seeds"]}
    graphs, manifests = {}, {}
    with tarfile.open(captures_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.name.endswith("/manifest.json"):
                continue
            history = Path(member.name).parent.name
            if history in graphs:
                raise ValueError("Duplicate captured history: " + history)
            manifest = json.load(archive.extractfile(member))
            graph = Graph(env=manifest["environment"])
            graph.nodes = {n["id"]: Node(**n) for n in manifest["nodes"]}
            graph.targets = manifest["targets"]
            graph.roots = set(manifest["mandatory_blobs"])
            if len(graph.targets) != config["versions"]:
                raise ValueError("Unexpected history version count: " + history)
            graphs[history], manifests[history] = graph, manifest
    if set(graphs) != expected_histories:
        raise ValueError("Captured history set differs from frozen grid: " + repr(sorted(set(graphs) ^ expected_histories)))
    module = load_source(hyppo_cache)
    output.mkdir(parents=True)
    (output / "protocol.json").write_bytes(protocol_path.read_bytes())
    records, errors, cache = [], [], {}
    source_hashes = {"audit_baseline_sensitivity.py": digest(__file__)}
    import recoverml.published_materializers as pm
    import recoverml.helix_materializer as hm
    import recoverml.witness as witness
    import recoverml.core as core
    import recoverml.capability_retention as capability
    import recoverml.robust_heuristics as heuristics
    for module_source in (pm, hm, witness, core, capability, heuristics):
        source_hashes[Path(module_source.__file__).name] = digest(module_source.__file__)
    start = dict(created_utc=datetime.now(timezone.utc).isoformat(),
        protocol_commit=protocol_commit, protocol_sha256=digest(protocol_path),
        captures_sha256=digest(captures_path), source_sha256=source_hashes,
        hyppo_revision=REVISION, hyppo_source_sha256=SOURCE_SHA256,
        histories=sorted(graphs), metadata_only=True)
    (output / "run_start.json").write_text(json.dumps(start, indent=2) + "\n")

    def coverage(history, scope, graph, caps, selected, weights):
        key = history, scope, tuple(sorted(selected))
        if key not in cache:
            faults = fault_sets(caps, config["loss_bound"])
            vectors = [certificate(restricted(graph, caps, fault), selected)["version_coverage"] for fault in faults]
            cache[key] = [[int(v[version]) for version in graph.targets] for v in vectors]
        vectors = cache[key]
        return (sum(sum(vector) for vector in vectors),
                sum(sum(w * ok for w, ok in zip(weights, vector)) for vector in vectors),
                len(vectors) * len(graph.targets), len(vectors) * sum(weights))

    for history in sorted(graphs):
        graph = graphs[history]
        ancestry = version_ancestry(graph)
        targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
        payload = sum(graph.sizes()[b] for b in targets - graph.roots)
        for scope in config["capability_scopes"]:
            caps = scopes(graph, scope)
            fixed = retained_bytes(graph, graph.roots, caps, config["loss_bound"])
            for fraction in config["optional_snapshot_budget_fractions"]:
                optional = math.floor(fraction * payload)
                budget = fixed + optional
                for profile, factors in config["cost_profiles"].items():
                    proxy = Graph(env=graph.env)
                    proxy.nodes = {nid: replace(node, compute_s=node.compute_s * factors.get(node.op, 1.0))
                                   for nid, node in graph.nodes.items()}
                    proxy.targets, proxy.roots = graph.targets, graph.roots
                    adapted = adapt(proxy)
                    for freq_name, weights in config["frequency_profiles"].items():
                        if len(weights) != len(graph.targets):
                            raise ValueError("Frequency profile length differs from versions")
                        for blob in graph.candidates:
                            adapted.nodes[blob]["frequency"] = max(1, sum(weight for weight, seen in zip(weights, ancestry) if blob in seen))
                        for eligibility, spec in config["eligibility_profiles"].items():
                            eligible = (graph.candidates if eligibility == "all" else targets if eligibility == "targets_only"
                                        else {n.blob for n in graph.nodes.values() if n.op in spec["operations"]})
                            for blob in graph.candidates:
                                adapted.nodes[blob]["type"] = "raw" if blob in graph.roots or blob not in eligible else "artifact"
                            for method in config["hyppo_methods"]:
                                chosen = (module.rank_based_materializer_frequency(adapted.nodes, optional + 1)
                                          if method == "HYPPO_frequency" else module.rank_based_materializer(adapted, optional + 1))
                                chosen = graph.roots | set(chosen)
                                actual = retained_bytes(graph, chosen, caps, config["loss_bound"])
                                exact, weighted, requests, weighted_total = coverage(history, scope, graph, caps, chosen, weights)
                                if actual > budget or not chosen - graph.roots <= eligible:
                                    errors.append(dict(history=history, scope=scope, check="budget_or_eligibility", method=method))
                                records.append(dict(history=history, scope=scope, k=config["loss_bound"],
                                    budget_fraction=fraction, budget_bytes=budget, retained_bytes=actual, optional_bytes=actual-fixed,
                                    method=method, cost_profile=profile, frequency_profile=freq_name, eligibility=eligibility,
                                    read_MiB_s=None, tie_order="native_hash", exact_structural_requests=exact, requests=requests,
                                    weighted_structural_requests=weighted, weighted_requests=weighted_total,
                                    complete=exact == requests, selected=sorted(chosen)))
                    for speed in config["helix_read_MiB_s"]:
                        for tie in config["helix_tie_orders"]:
                            chosen, _ = helix(proxy, optional, speed * 1024 ** 2, reverse_ties=tie == "reverse")
                            actual = retained_bytes(graph, chosen, caps, config["loss_bound"])
                            exact, weighted, requests, weighted_total = coverage(history, scope, graph, caps, chosen, [1] * len(graph.targets))
                            if actual > budget:
                                errors.append(dict(history=history, scope=scope, check="budget", method="HELIX_rule"))
                            records.append(dict(history=history, scope=scope, k=config["loss_bound"],
                                budget_fraction=fraction, budget_bytes=budget, retained_bytes=actual, optional_bytes=actual-fixed,
                                method="HELIX_rule", cost_profile=profile, frequency_profile="not_used", eligibility="all",
                                read_MiB_s=speed, tie_order=tie, exact_structural_requests=exact, requests=requests,
                                weighted_structural_requests=weighted, weighted_requests=weighted_total,
                                complete=exact == requests, selected=sorted(chosen)))
        print(json.dumps(dict(completed_history=history, rows=len(records))), flush=True)
    fields = [field for field in records[0] if field != "selected"]
    with (output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in records)
    with gzip.open(output / "selections.json.gz", "wt") as stream:
        json.dump(records, stream, allow_nan=False)
    common = len(graphs) * len(config["capability_scopes"]) * len(config["optional_snapshot_budget_fractions"]) * len(config["cost_profiles"])
    expected_hyppo = common * len(config["frequency_profiles"]) * len(config["eligibility_profiles"]) * len(config["hyppo_methods"])
    expected_helix = common * len(config["helix_read_MiB_s"]) * len(config["helix_tie_orders"])
    if len(records) != expected_hyppo + expected_helix:
        errors.append(dict(check="incomplete_grid", expected=expected_hyppo + expected_helix, actual=len(records)))
    report = dict(status="PASS" if not errors else "FAIL", histories=len(graphs), rows=len(records),
        expected_rows=expected_hyppo + expected_helix, expected_hyppo_rows=expected_hyppo,
        expected_helix_rows=expected_helix, unique_structural_coverage_evaluations=len(cache), errors=errors,
        finished_utc=datetime.now(timezone.utc).isoformat(), summary_sha256=digest(output / "summary.csv"),
        selections_sha256=digest(output / "selections.json.gz"),
        interpretation="Complete structural decision sensitivity only; no fresh replay or latency measurements",
        limitations=["These histories were constructed from public recipes rather than sampled production traces",
            "Declared recovery weights are sensitivity assumptions rather than observed access frequencies",
            "The captured physical-ancestry adapter is not the native HYPPO hyperpath estimator",
            "HELIX frequency and restricted-eligibility variants are not claimed",
            "A robust partial-coverage optimum is not computed in this baseline-only sweep"])
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if errors:
        raise RuntimeError("Sensitivity grid invariants failed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path("configs/scientific_sensitivity_oct15.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hyppo-cache", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.captures, args.protocol, args.output, args.hyppo_cache), indent=2))
