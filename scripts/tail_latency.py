"""Export measured latency percentiles and empirical CDF data.

Usage: python scripts/tail_latency.py results/archive/iteration2 --out results/tail_iteration2

Groups by workload and budget so unlike workloads are not silently pooled.
Only exact successful restorations contribute latency samples; all requests
remain in coverage counts. This is post-processing, not a new benchmark.
CPU traces, timestamps and throughput require a separately instrumented run.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def percentile(values, q):
    """Linear interpolation between sorted samples (including singleton input)."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def export(source, output):
    raw = source.read_bytes()
    groups = defaultdict(list)
    with source.open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["case_id"].split("-rep")[0], row["policy"], row["budget_fraction"])
            groups[key].append(row)
    summaries, cdf = [], []
    for (workload, policy, budget), rows in sorted(groups.items()):
        times = []
        for row in rows:
            if row["exact"].lower() == "true":
                value = float(row["restore_s"]) * 1000
                if not math.isfinite(value) or value < 0:
                    raise ValueError("Invalid measured successful restore latency")
                times.append(value)
        common = dict(workload=workload, policy=policy, budget_fraction=budget)
        summaries.append(dict(
            **common, total_requests=len(rows), exact_requests=len(times),
            budget_blocked=sum(r["within_budget"].lower() != "true" for r in rows),
            successful_latency_samples=len(times),
            p50_ms=percentile(times, .50), p90_ms=percentile(times, .90),
            p99_ms=percentile(times, .99),
            max_ms=max(times) if times else None,
        ))
        ordered = sorted(times)
        # Emit one point per distinct latency so ties have the correct ECDF.
        for index, value in enumerate(ordered):
            if index == len(ordered) - 1 or ordered[index + 1] != value:
                cdf.append(dict(**common, latency_ms=value,
                                cumulative_fraction=(index + 1) / len(ordered),
                                samples=len(ordered)))
    output.mkdir(parents=True, exist_ok=False)
    for name, records, fields in (
        ("latency_percentiles.csv", summaries,
         ["workload", "policy", "budget_fraction", "total_requests",
          "exact_requests", "budget_blocked", "successful_latency_samples",
          "p50_ms", "p90_ms", "p99_ms", "max_ms"]),
        ("latency_cdf.csv", cdf,
         ["workload", "policy", "budget_fraction", "latency_ms",
          "cumulative_fraction", "samples"]),
    ):
        with (output / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
    metadata = dict(source=str(source), source_sha256=hashlib.sha256(raw).hexdigest(),
                    total_requests=sum(len(v) for v in groups.values()),
                    percentile_method="linear interpolation",
                    latency_population="exact successful restores only",
                    timing_scope="restore_s as recorded by the original harness",
                    run_type="post-processing of existing measurements")
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.directory / "raw_requests.csv", args.out), indent=2))
