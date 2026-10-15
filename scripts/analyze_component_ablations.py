"""Independently scan and reconcile every saved structural ablation certificate."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

from audit_component_ablations import (fixtures, logical_identity, no_alternative_producers,
    read_graph, scan_certificate, scopes)
from recoverml.capability_retention import retained_bytes, restricted
from recoverml.robust_heuristics import fault_sets
from recoverml.witness import certificate


def analyze(root, captures):
    root, captures = Path(root), Path(captures)
    config = json.loads((root / "protocol.json").read_text())
    receipt = json.loads((root / "run_start.json").read_text())
    rows = json.loads((root / "records.json").read_text())
    cases, errors = {}, []
    for workflow in config["workflows"]:
        name = f"{workflow}-{config['seed']}"
        path = captures / name / "manifest.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["input_manifests_sha256"][name]:
            raise ValueError("Captured input differs from timed run: " + name)
        graph = read_graph(path)
        for k in config["loss_bounds"]:
            cases[f"{name}-k{k}"] = graph, scopes(graph, config["scope"]), k
    cases.update(fixtures())
    expected = set(itertools.product(cases, range(config["repetitions"]), config["controls"]))
    actual = [(r["case"], r["trial"], r["control"]) for r in rows]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        errors.append("Recorded rows differ from the full declared grid")
    checked, completed = 0, 0
    for row in rows:
        graph, caps, k = cases[row["case"]]
        if row["control"] == "no_alternative_producers": graph, caps = no_alternative_producers(graph, caps)
        elif row["control"] == "logical_identity": graph, caps = logical_identity(graph, caps)
        chosen = set(row["selected"])
        if not graph.roots <= chosen <= graph.candidates:
            errors.append(dict(case=row["case"], control=row["control"], error="Invalid chosen identities"))
        if retained_bytes(graph, chosen, caps, k) != row["retained_bytes"]:
            errors.append(dict(case=row["case"], error="Retained byte mismatch"))
        for fault in fault_sets(caps, k):
            view = restricted(graph, caps, fault)
            indexed = certificate(view, chosen)
            scanned = scan_certificate(view, chosen)
            match = (set(indexed["available"]) == set(scanned["available"])
                and indexed["version_coverage"] == scanned["version_coverage"])
            checked += 1
            completed += scanned["complete"]
            if not match or row["status"] == "ok" and not scanned["complete"]:
                errors.append(dict(case=row["case"], trial=row["trial"], control=row["control"], fault=sorted(fault), error="Independent closure disagreement"))
    report = dict(status="PASS" if not errors else "FAIL", rows=len(rows), expected_rows=len(expected),
        independent_indexed_vs_full_scan_comparisons=checked, complete_structural_certificates=completed,
        errors=errors, analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        records_sha256=hashlib.sha256((root / "records.json").read_bytes()).hexdigest(),
        interpretation="New independent structural reconciliation of saved selections, not new timed optimizer or disk-recovery measurements")
    (root / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    if errors:
        raise ValueError(errors)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--captures", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.directory, args.captures), indent=2))
