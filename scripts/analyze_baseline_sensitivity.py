"""Reconcile the frozen metadata-only sensitivity grid and expose negative results."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path


def analyze(root):
    root = Path(root)
    protocol = json.loads((root / "protocol.json").read_text())
    with gzip.open(root / "selections.json.gz", "rt") as stream:
        rows = json.load(stream)
    with (root / "summary.csv").open() as stream:
        summary = list(csv.DictReader(stream))
    expected_histories = {f"{w}-{s}" for w in protocol["workflows"] for s in protocol["seeds"]}
    fields = ("history", "scope", "budget_fraction", "cost_profile", "frequency_profile", "eligibility", "method", "read_MiB_s", "tie_order")
    keys = [tuple(r[f] for f in fields) for r in rows]
    common = len(expected_histories) * len(protocol["capability_scopes"]) * len(protocol["optional_snapshot_budget_fractions"]) * len(protocol["cost_profiles"])
    expected_hyppo = common * len(protocol["frequency_profiles"]) * len(protocol["eligibility_profiles"]) * len(protocol["hyppo_methods"])
    expected_helix = common * len(protocol["helix_read_MiB_s"]) * len(protocol["helix_tie_orders"])
    errors = []
    if len(rows) != expected_hyppo + expected_helix or len(summary) != len(rows):
        errors.append("Incomplete declared row count")
    if len(set(keys)) != len(keys):
        errors.append("Duplicate condition")
    if {r["history"] for r in rows} != expected_histories:
        errors.append("Missing declared histories")
    for index, (row, saved) in enumerate(zip(rows, summary)):
        if row["retained_bytes"] > row["budget_bytes"]:
            errors.append(f"Budget overrun at row {index}")
        if not 0 <= row["exact_structural_requests"] <= row["requests"]:
            errors.append(f"Coverage count at row {index}")
        if any(str(row[f]) != saved[f] for f in ("history", "scope", "method", "retained_bytes", "requests", "exact_structural_requests")):
            errors.append(f"CSV/selection mismatch at row {index}")
    changes = {}
    for dimension, baseline in (("cost_profile", "nominal"), ("frequency_profile", "uniform"), ("eligibility", "all"), ("read_MiB_s", 200), ("tie_order", "capture")):
        lookup = {tuple(r[f] for f in fields if f != dimension): r for r in rows if r[dimension] == baseline}
        pairs = []
        for row in rows:
            if row[dimension] == baseline:
                continue
            reference = lookup.get(tuple(row[f] for f in fields if f != dimension))
            if reference is not None:
                pairs.append((reference, row))
        changes[dimension] = dict(baseline=baseline, comparisons=len(pairs),
            selected_set_changed=sum(a["selected"] != b["selected"] for a, b in pairs),
            exact_request_count_changed=sum(a["exact_structural_requests"] != b["exact_structural_requests"] for a, b in pairs),
            retained_byte_count_changed=sum(a["retained_bytes"] != b["retained_bytes"] for a, b in pairs))
    by_method = {method: dict(rows=sum(r["method"] == method for r in rows),
        complete_conditions=sum(r["method"] == method and r["complete"] for r in rows))
        for method in sorted({r["method"] for r in rows})}
    report = dict(status="PASS" if not errors else "FAIL", rows=len(rows), expected_rows=expected_hyppo + expected_helix,
        expected_hyppo_rows=expected_hyppo, expected_helix_rows=expected_helix, histories=len(expected_histories),
        method_counts=by_method, paired_annotation_changes=changes, errors=errors,
        summary_sha256=hashlib.sha256((root / "summary.csv").read_bytes()).hexdigest(),
        interpretation="Structural decision sensitivity only. These are not new executions or independent experimental samples.")
    (root / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Baseline annotation sensitivity", "", f"Status: **{report['status']}** and {len(rows)} metadata-only conditions across {len(expected_histories)} frozen captures", "",
        "The pinned HYPPO functions and the tested HELIX rule were run with nonuniform operation-cost changes and declared access weights and eligibility controls. Coverage uses the same captured graphs and fault sets. No model training or disk restoration or recovery timing was performed by this sweep.", "",
        "| Changed annotation | Paired comparisons | Selected set changes | Exact request-count changes |", "|---|---:|---:|---:|"]
    for name, item in changes.items():
        lines.append(f"| {name} | {item['comparisons']} | {item['selected_set_changed']} | {item['exact_request_count_changed']} |")
    lines += ["", "Zero changes remain part of the result. Changes in access weights are assumptions rather than observed scientific access frequencies. Repeated annotations on one captured graph are correlated controls and do not increase the number of independent workflows. This baseline-only sweep does not establish an optimal partial-coverage bound or native full-system performance.", ""]
    (root / "RESULTS.md").write_text("\n".join(lines))
    if errors:
        raise ValueError(errors)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(analyze(parser.parse_args().directory), indent=2))
