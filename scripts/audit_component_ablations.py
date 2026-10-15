"""Predeclared structural component controls without changing historical data."""
import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from recoverml.core import Graph, Node
from recoverml.capability_retention import optimize as counterexample, retained_bytes, restricted
from recoverml.component_retention import components, optimize as decomposed
from recoverml.robust_retention import optimize as automatic
from recoverml.scenario_retention import optimize as scenario
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate
from audit_baseline_sensitivity import frozen_protocol, scopes


def read_graph(path):
    data = json.loads(Path(path).read_text())
    return Graph(nodes={n["id"]: Node(**n) for n in data["nodes"]},
        targets=data["targets"], roots=set(data["mandatory_blobs"]), env=data["environment"])


def no_alternative_producers(graph, capabilities):
    """A different available-producer contract; preserve captured provenance."""
    seen = set()
    output = Graph(env=graph.env, targets=graph.targets, roots=set(graph.roots))
    for nid, node in graph.nodes.items():
        keep = node.replayable and node.blob not in seen
        if node.replayable:
            seen.add(node.blob)
        output.nodes[nid] = replace(node, replayable=keep)
    return output, {n: c for n, c in capabilities.items() if output.nodes[n].replayable}


def logical_identity(graph, capabilities):
    """Metadata-only counterfactual; logical IDs are not artifact content hashes."""
    output = Graph(env=graph.env, targets=graph.targets)
    for nid, node in graph.nodes.items():
        identity = "logical:" + nid
        output.nodes[nid] = replace(node, blob=identity)
        if node.blob in graph.roots:
            output.roots.add(identity)
    return output, dict(capabilities)


def no_root_shortcut(graph, capabilities, k, time_limit_s):
    """Use the same exact root-conditioned components with no atomic shortcut."""
    targets = {graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    selected, records = set(graph.roots), []
    for component in components(graph):
        if not component & targets:
            continue
        live = [n for n in graph.nodes.values() if n.replayable and n.blob in component]
        roots = {graph.nodes[d].blob for n in live for d in n.deps} & graph.roots
        projection = Graph(env=graph.env, roots=set(roots))
        for nid, node in graph.nodes.items():
            if node.blob in component | roots:
                projection.nodes[nid] = (replace(node, deps=[], replayable=False)
                    if node.blob in roots or not node.replayable else node)
        projection.targets = {v: [t for t in ts if graph.nodes[t].blob in component]
            for v, ts in graph.targets.items() if any(graph.nodes[t].blob in component for t in ts)}
        caps = {n: c for n, c in capabilities.items() if n in projection.nodes and projection.nodes[n].replayable}
        chosen, status, diag = automatic(projection, caps, k, time_limit_s=time_limit_s)
        records.append(diag)
        if status != "ok":
            return selected, status, dict(robust_certified=False, storage_optimal=False, components=records)
        selected |= chosen & component
    return selected, "ok", dict(robust_certified=True, storage_optimal=True, components=records)


def scan_certificate(graph, retained):
    """Independent finite Horn fixed-point reference rather than an index mirror."""
    available = set(retained)
    while True:
        following = available | {n.blob for n in graph.nodes.values() if n.replayable
            and all(graph.nodes[d].blob in available for d in n.deps)}
        if following == available:
            break
        available = following
    coverage = {v: all(graph.nodes[t].blob in available for t in ts) for v, ts in graph.targets.items()}
    return dict(available=sorted(available), version_coverage=coverage, complete=all(coverage.values()))


def fixtures():
    result = {}
    graph = Graph(env={})
    root = graph.add("root", [], {}, b"r" * 16, False, "root", 0., 0, mandatory=True)
    caps = {}
    targets = []
    for i in range(4):
        node = graph.add("fixture", [root], {"i": i}, bytes([i]) * 100, True, "stage", .01, 0)
        caps[node] = "stage" + str(i % 2)
        targets.append(node)
    graph.targets = {"0": targets}
    result["shared_root_frontiers"] = graph, caps, 1
    graph = Graph(env={})
    root = graph.add("root", [], {}, b"r" * 16, False, "root", 0., 0, mandatory=True)
    a = graph.add("first", [root], {}, b"same" * 100, True, "A", .01, 0)
    b = graph.add("second", [root], {}, b"same" * 100, True, "B", .01, 0)
    graph.targets = {"0": [a]}
    result["alternative_producers"] = graph, {a: "A", b: "B"}, 1
    graph = Graph(env={})
    root = graph.add("root", [], {}, b"r" * 16, False, "root", 0., 0, mandatory=True)
    target = graph.add("opaque", [], {}, b"target" * 32, False, "history", 0., 0)
    cyclic = graph.add("cycle", [target], {}, b"target" * 32, True, "cycle", .01, 0)
    grounded = graph.add("first", [root], {}, b"target" * 32, True, "A", .01, 0)
    graph.targets = {"0": [target]}
    result["alias_cycle"] = graph, {cyclic: "cycle", grounded: "A"}, 1
    return result


def chain_graph(length):
    graph = Graph(env={})
    previous = graph.add("root", [], {}, 0, False, "root", 0., 0, mandatory=True)
    for i in range(1, length + 1):
        previous = graph.add("chain", [previous], {"i": i}, i, True, "chain", .01, 0)
    graph.targets = {"0": [previous]}
    return graph


def run(captures, protocol_path, output):
    committed = frozen_protocol(protocol_path)
    config = json.loads(protocol_path.read_text())
    if output.exists():
        raise ValueError("Refusing to overwrite evidence")
    cases, input_hashes = {}, {}
    for workflow in config["workflows"]:
        name = f"{workflow}-{config['seed']}"
        path = Path(captures) / name / "manifest.json"
        graph = read_graph(path)
        input_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for k in config["loss_bounds"]:
            cases[f"{name}-k{k}"] = graph, scopes(graph, config["scope"]), k
    cases.update(fixtures())
    if set(fixtures()) != set(config["fixtures"]):
        raise ValueError("Fixture protocol differs from implementation")
    output.mkdir(parents=True)
    (output / "protocol.json").write_bytes(protocol_path.read_bytes())
    import recoverml.component_retention as component_source
    import recoverml.capability_retention as capability_source
    import recoverml.scenario_retention as scenario_source
    import recoverml.witness as witness_source
    sources = [Path(__file__), Path(component_source.__file__), Path(capability_source.__file__), Path(scenario_source.__file__), Path(witness_source.__file__)]
    (output / "run_start.json").write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),
        protocol_commit=committed, protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        input_manifests_sha256=input_hashes, source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        metadata_only=True, original_artifact_payloads_loaded=False), indent=2) + "\n")
    rows, detailed, archive, errors = [], [], [], []
    for name, (original, caps, k) in cases.items():
        archive.append(dict(case=name, captured_logical_outputs=len(original.nodes), unique_physical_outputs=len(original.candidates),
            logical_output_bytes=sum(n.size for n in original.nodes.values()),
            unique_physical_output_bytes=sum(original.sizes().values()),
            deduplicated_output_bytes_saved=sum(n.size for n in original.nodes.values())-sum(original.sizes().values())))
        for trial in range(config["repetitions"]):
            controls = config["controls"][trial:] + config["controls"][:trial]
            for control in controls:
                graph, local_caps = original, caps
                function = decomposed
                if control == "no_decomposition": function = automatic
                elif control == "no_root_shortcut": function = no_root_shortcut
                elif control == "forced_scenario_no_decomposition": function = scenario
                elif control == "forced_counterexample_no_decomposition": function = counterexample
                elif control == "no_alternative_producers": graph, local_caps = no_alternative_producers(original, caps)
                elif control == "logical_identity": graph, local_caps = logical_identity(original, caps)
                started = time.perf_counter()
                chosen, status, diag = function(graph, local_caps, k, time_limit_s=config["per_solver_call_time_limit_s"])
                elapsed = time.perf_counter() - started
                faults = fault_sets(local_caps, k)
                checks = [certificate(restricted(graph, local_caps, fault), chosen)["complete"] for fault in faults]
                if status == "ok" and (not all(checks) or not diag.get("storage_optimal")):
                    errors.append(dict(case=name, trial=trial, control=control, error="False certification"))
                row = dict(case=name, trial=trial, control=control, same_contract=control in config["same_contract_controls"],
                    k=k, status=status, robust=all(checks), storage_optimal=bool(diag.get("storage_optimal")),
                    retained_bytes=retained_bytes(graph, chosen, local_caps, k),
                    retained_payload_bytes=sum(graph.sizes()[b] for b in chosen),
                    elapsed_s=elapsed, optional_artifacts=len(chosen-graph.roots),
                    fault_scenarios_checked=len(faults), selected=sorted(chosen))
                rows.append(row)
                detailed.append(dict(**row, diagnostic=diag))
        print(json.dumps(dict(completed_case=name, rows=len(rows))), flush=True)
    comparisons = 0
    for name in cases:
        originals = [r for r in rows if r["case"] == name and r["same_contract"] and r["status"] == "ok"]
        if originals and len({r["retained_bytes"] for r in originals}) != 1:
            errors.append(dict(case=name, error="Same-contract certified byte objectives disagree"))
        comparisons += max(0, len(originals)-1)
    chain_records = []
    for length in config["certificate_controls"]["chain_lengths"]:
        graph = chain_graph(length)
        for trial in range(config["certificate_controls"]["repetitions"]):
            started = time.perf_counter(); fast = certificate(graph, graph.roots); indexed_s = time.perf_counter()-started
            started = time.perf_counter(); slow = scan_certificate(graph, graph.roots); scanned_s = time.perf_counter()-started
            match = set(fast["available"]) == set(slow["available"]) and fast["version_coverage"] == slow["version_coverage"]
            chain_records.append(dict(length=length, trial=trial, match=match, indexed_s=indexed_s, scan_s=scanned_s))
            if not match: errors.append(dict(chain_length=length, error="Certificate disagreement"))
    with (output / "summary.csv").open("w", newline="") as stream:
        fields = [f for f in rows[0] if f != "selected"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows({f:r[f] for f in fields} for r in rows)
    (output / "records.json").write_text(json.dumps(detailed, indent=2) + "\n")
    (output / "archive_output_accounting.json").write_text(json.dumps(archive, indent=2) + "\n")
    (output / "certificate_controls.json").write_text(json.dumps(chain_records, indent=2) + "\n")
    expected = (len(config["workflows"])*len(config["loss_bounds"])+len(config["fixtures"])) * config["repetitions"] * len(config["controls"])
    if len(rows) != expected: errors.append(dict(error="Incomplete declared matrix", actual=len(rows), expected=expected))
    report = dict(status="PASS" if not errors else "FAIL", rows=len(rows), expected_rows=expected,
        same_contract_rows=sum(r["same_contract"] for r in rows), cases=len(cases),
        uncertified_rows=sum(r["status"] != "ok" for r in rows),
        certified_same_contract_objective_comparisons=comparisons,
        enumerated_fault_certificate_checks=sum(r["fault_scenarios_checked"] for r in rows),
        indexed_reference_chain_comparisons=len(chain_records), errors=errors,
        finished_utc=datetime.now(timezone.utc).isoformat(),
        summary_sha256=hashlib.sha256((output / "summary.csv").read_bytes()).hexdigest(),
        limitations=["Captured public-recipe histories and constructed fixtures, not independent production traces",
            "Metadata-only planner controls and structural certificates, no fresh historical disk recovery",
            "Different-contract rows are not same-objective speedup evidence",
            "Timing includes single-host order effects and two repetitions provide descriptive checks only",
            "Time limit applies to individual solver calls rather than a strict process deadline"])
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path("configs/component_ablations_oct15.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.captures, args.protocol, args.output), indent=2))
