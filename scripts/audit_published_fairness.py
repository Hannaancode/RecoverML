"""Read-only audit of archived published-component comparisons.

This does not retrain models or execute historical recovery. It recomputes
counts, budgets, structural coverage and a declared adapter sensitivity from
the archived manifests and traces. Original experiment files are never changed.
"""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import platform
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from recoverml.capability_retention import contract, retained_bytes, restricted
from recoverml.core import Graph, Node
from recoverml.published_materializers import (
    REVISION, SOURCE_SHA256, adapt, load_source,
)
from recoverml.witness import certificate


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(published, hyppo_cache):
    names = ["summary.csv", "execution_traces.json.gz",
             "planner_certificates.json.gz", "stores.tar.gz", "report.json"]
    hashes = {name: sha256(published / name) for name in names}
    with (published / "summary.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    traces = json.loads(gzip.decompress((published / names[1]).read_bytes()))
    plans = json.loads(gzip.decompress((published / names[2]).read_bytes()))
    plan_by_case = {p["case"]: p for p in plans}
    summary = {(r["case"], r["policy"]): r for r in rows}
    by_request = defaultdict(list)
    errors = []
    checked = Counter()
    totals = defaultdict(Counter)
    for trace in traces:
        by_request[trace["case"], trace["policy"]].append(trace)
        caps = plan_by_case[trace["case"]]["capabilities"]
        violations = [event["producer"] for event in trace["events"]
                      if event.get("producer") and
                      caps.get(event["producer"]) in trace["disabled"]]
        if violations:
            errors.append(dict(check="disabled_producer", case=trace["case"],
                               policy=trace["policy"], producers=violations))
        checked["trace_disabled_producer_checks"] += 1
    scenario_sets = {}
    for row in rows:
        key = row["case"], row["policy"]
        group = by_request[key]
        if len(group) != int(row["requests"]) or sum(t["exact"] for t in group) != int(row["exact"]):
            errors.append(dict(check="summary_trace_counts", case=key[0], policy=key[1]))
        if sum(t["expected_blocked"] for t in group) != int(row["blocked"]):
            errors.append(dict(check="summary_blocked_counts", case=key[0], policy=key[1]))
        scenarios = {tuple(sorted(t["disabled"])) for t in group}
        if key[0] in scenario_sets and scenarios != scenario_sets[key[0]]:
            errors.append(dict(check="identical_scenario_sets", case=key[0], policy=key[1]))
        scenario_sets[key[0]] = scenarios
        if key[1] != "HELIX_snapshot_budget" and int(row["retained_bytes"]) > int(row["robust_budget"]):
            errors.append(dict(check="common_budget", case=key[0], policy=key[1]))
        totals[key[1]].update(requests=len(group), exact=sum(t["exact"] for t in group),
                               expected_blocked=sum(t["expected_blocked"] for t in group), rows=1)
        checked["summary_rows"] += 1
    module = load_source(hyppo_cache)
    sensitivity = []
    with tarfile.open(published / "stores.tar.gz", "r:gz") as archive:
        members = {m.name: m for m in archive.getmembers()}

        def resolve(member):
            seen = set()
            while member.islnk():
                if member.name in seen:
                    raise ValueError("Cyclic hard link in archived evidence")
                seen.add(member.name)
                member = members[member.linkname]
            if not member.isfile():
                raise ValueError("Unexpected non-file in archived evidence")
            return member

        # Cache decoded manifests by their regular-file archive member. Hard
        # links count in every policy's logical store, not as zero-byte payloads.
        decoded = {}

        def manifest_for(name):
            actual = resolve(members[name])
            if actual.name not in decoded:
                decoded[actual.name] = json.load(archive.extractfile(actual))
            return decoded[actual.name]

        store_files = defaultdict(list)
        for name, member in members.items():
            parts = name.split("/")
            if len(parts) >= 3 and (member.isfile() or member.islnk()):
                store_files[parts[0], parts[1]].append(member)
        for key, row in summary.items():
            prefix = "/".join(key)
            manifest = manifest_for(prefix + "/manifest.json")
            graph = Graph(env=manifest["environment"])
            graph.nodes = {n["id"]: Node(**n) for n in manifest["nodes"]}
            graph.targets = manifest["targets"]
            graph.roots = set(manifest["mandatory_blobs"])
            caps = plan_by_case[key[0]]["capabilities"]
            k = int(row["k"])
            expected_manifest = manifest_for(key[0] + "/RecoverML_decomposed/manifest.json")
            if manifest != expected_manifest:
                errors.append(dict(check="identical_graph_environment", case=key[0], policy=key[1]))
            selected = set(plan_by_case[key[0]]["selected"][key[1]])
            payloads = {Path(m.name).stem: resolve(m).size for m in store_files[key]
                        if "/blobs/" in m.name and m.name.endswith(".pkl")}
            if set(payloads) != selected or any(graph.sizes().get(b) != size for b, size in payloads.items()):
                errors.append(dict(check="selected_payload_sizes", case=key[0], policy=key[1]))
            actual_bytes = sum(resolve(m).size for m in store_files[key])
            if actual_bytes != int(row["retained_bytes"]) or actual_bytes != retained_bytes(graph, selected, caps, k):
                errors.append(dict(check="actual_archived_file_bytes", case=key[0], policy=key[1], actual=actual_bytes))
            contract_member = resolve(members[prefix + "/capability_contract.json"])
            if archive.extractfile(contract_member).read() != contract(caps, k):
                errors.append(dict(check="capability_contract", case=key[0], policy=key[1]))
            coverage = {}
            for lost in sorted(scenario_sets[key[0]]):
                coverage[lost] = certificate(restricted(graph, caps, lost), selected)["version_coverage"]
            for trace in by_request[key]:
                if bool(trace["exact"]) != bool(coverage[tuple(sorted(trace["disabled"]))][trace["version"]]):
                    errors.append(dict(check="structural_vs_actual_trace", case=key[0], policy=key[1], version=trace["version"]))
            checked["archived_policy_stores"] += 1
            if key[1] != "RecoverML_decomposed":
                continue
            costs, ancestors = {}, {}
            for nid, node in graph.nodes.items():
                seen = {nid}
                for dependency in node.deps:
                    seen |= ancestors[dependency]
                ancestors[nid] = seen
                costs[nid] = sum(graph.nodes[a].compute_s for a in seen)
            adapted = adapt(graph)
            for blob in graph.candidates:
                adapted.nodes[blob]["cc"] = min(costs[n.id] for n in graph.nodes.values() if n.blob == blob)
            optional = int(row["robust_budget"]) - retained_bytes(graph, graph.roots, caps, k)
            for policy, frequency in [("HYPPO_rank", False), ("HYPPO_frequency", True)]:
                result = (module.rank_based_materializer_frequency(adapted.nodes, optional + 1)
                          if frequency else module.rank_based_materializer(adapted, optional + 1))
                candidate = graph.roots | set(result)
                count = sum(sum(certificate(restricted(graph, caps, lost), candidate)["version_coverage"].values())
                            for lost in scenario_sets[key[0]])
                old = summary[key[0], policy]
                sensitivity.append(dict(case=key[0], policy=policy, old_max_ancestry_exact=int(old["exact"]),
                    min_ancestry_structural_coverage=count, requests=int(old["requests"]),
                    selected_set_changed=candidate != set(plan_by_case[key[0]]["selected"][policy]),
                    minimum_ancestry_retained_bytes=retained_bytes(graph, candidate, caps, k)))
    source = Path(__file__).resolve()
    return dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(),
        audit_kind="Read-only archived-evidence audit and structural adapter sensitivity; no new recovery execution",
        status="PASS" if not errors else "FAIL", errors=errors, checked=dict(checked),
        cases=len(plans), traces=len(traces), policy_totals={k: dict(v) for k, v in sorted(totals.items())},
        hyppo_revision=REVISION, hyppo_expected_source_sha256=SOURCE_SHA256,
        hyppo_actual_source_sha256=sha256(Path(hyppo_cache) / "history_manager.py"),
        source_hashes=hashes, audit_source_sha256=sha256(source),
        python_version=platform.python_version(),
        sensitivity=dict(change="Replace maximum captured logical-ancestry compute cost with minimum across producers",
            scope="Annotation sensitivity only; minimum ancestry is not a full minimum-hyperpath cost estimator",
            selected_set_changed_cases=sum(r["selected_set_changed"] for r in sensitivity),
            coverage_changed_cases=sum(r["old_max_ancestry_exact"] != r["min_ancestry_structural_coverage"] for r in sensitivity),
            rows=sensitivity),
        limitations=[
            "The PASS applies to these recorded invariants, not to complete scientific validity or native baseline fidelity",
            "HYPPO released ranking functions omit the paper's depth/locality weighting and complete hyperpath cost estimator",
            "All stores use the project-supplied captured-graph and physical-blob adapters",
            "The common main budget is the RecoverML robust optimum; only HELIX has a separate larger-budget control in this suite",
            "File sizes use resolved archive headers; this script does not independently deserialize or rerun every stored model",
            "Structural certificate checks reuse the current project certificate implementation",
            "The sensitivity is retrospective and must not be represented as a preregistered new execution study",
        ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--published", type=Path, default=Path("results/research/paper_oct14/published"))
    parser.add_argument("--hyppo-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new destination to preserve evidence")
    report = run(args.published, args.hyppo_cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "cases", "traces", "checked")}, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
