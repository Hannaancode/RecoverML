"""Audit saved experimental evidence without rerunning or editing old results.

The inventory includes ignored local runs when they are present.  Their absence
from a clean clone is recorded rather than treated as proof they never existed.
Request counts are coverage denominators, never independent sample sizes.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def relative(path, root):
    return str(path.relative_to(root))


def experiment_directories(root):
    found = set()
    for base in ("archive", "milestone2", "research", "runs"):
        directory = root / "results" / base
        if not directory.exists():
            continue
        for candidate in directory.iterdir():
            if not candidate.is_dir():
                continue
            if candidate.name in ("paper_oct14", "capability_loss_oct13") and base == "research":
                found.update(p for p in candidate.iterdir() if p.is_dir())
            else:
                found.add(candidate)
    return sorted(found)


def source_catalogue(root, tracked):
    catalogue = defaultdict(list)
    sources = []
    candidates = set((root / "src").rglob("*.py")) | set((root / "scripts").glob("*.py"))
    candidates |= set((root / "results").glob("**/source_snapshot/*.py"))
    candidates |= set((root / "results/validation").glob("**/recovered_source_versions/*.py"))
    for path in sorted(candidates):
        name = relative(path, root)
        identity = sha(path)
        catalogue[identity].append(name)
        sources.append(dict(path=name, sha256=identity, tracked=name in tracked,
                            source_snapshot="/source_snapshot/" in name or "/recovered_source_versions/" in name,
                            executable_entrypoint="__main__" in path.read_text()))
    # An older source can be absent from the current checkout and still be
    # recoverable exactly from genuine local Git history.  Do not call it lost.
    references = {}
    for line in subprocess.check_output(
            ["git", "rev-list", "--objects", "--all", "--", "src/recoverml", "scripts"],
            cwd=root, text=True).splitlines():
        fields = line.split(" ", 1)
        if len(fields) == 2 and fields[1].endswith(".py"):
            references[fields[0]] = fields[1]
    historical_sources = []
    for oid, path in references.items():
        raw = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=root)
        identity = hashlib.sha256(raw).hexdigest()
        reference = "git-object:" + oid + ":" + path
        catalogue[identity].append(reference)
        historical_sources.append(dict(path=path, git_blob_sha1=oid, sha256=identity,
            scope="Read-only local Git object; remote branch reachability not checked by this lookup"))
    return dict(catalogue), sources, historical_sources


def classify(path, files, record, archive_runs):
    name = str(path)
    if path.name == "source_snapshot":
        return "source_provenance", "Source copies rather than a separate experiment"
    if path.name in ("analysis", "extension_analysis") or "guide_verified_" in path.name and "smoke" not in path.name:
        return "derived_analysis", "Saved-data analysis rather than new independent observations"
    if path.name == "diagnostics" or "diagnostic" in path.name:
        return "preserved_diagnostic", "Excluded from final quality claims; inspect preserved diagnostics"
    if path.name == "protocol_pilot" or path.name == "paper_tabular_oct14":
        return "superseded_protocol_pilot", "Strict integer capacity pilot; not a final comparison"
    if "failed" in path.name:
        return "incomplete_local_diagnostic", "Directory name records failure; terminal error and cause may be unavailable"
    if path.name == "paper_estimators_oct14":
        return "incomplete_local_diagnostic", "Neural serialization failure is separately preserved in paper diagnostics"
    if not files:
        return "empty_directory", "No evidence files are present"
    if name in archive_runs:
        return "working_copy_of_published_evidence", "Copied into the named research evidence group; do not count twice"
    if "/runs/" in name and not any(n in record for n in ("report.json", "summary.json", "audit.json", "provenance.json")):
        return "unresolved_local_working_directory", "No completion report; selection history cannot be reconstructed from directory presence"
    if any(n in record for n in ("report.json", "summary.json", "audit.json")) or (path / "RUN_COMPLETE").exists():
        return "saved_evidence", "Completion and scope require checking the report; not inferred from request totals"
    return "saved_partial_or_supporting_evidence", "Supporting files exist but no standard completion report"


def headline_audit(root):
    base = root / "results/research/paper_oct14"
    output = {}
    for group in ("tabular", "estimators", "published"):
        folder = base / group
        summary = rows(folder / "summary.csv")
        raw = gzip.decompress((folder / "execution_traces.json.gz").read_bytes())
        traces = json.loads(raw)
        report = read_json(folder / "report.json")
        grouped = defaultdict(lambda: [0, 0])
        identities = []
        for trace in traces:
            grouped[trace["case"], trace["policy"]][0] += 1
            grouped[trace["case"], trace["policy"]][1] += int(trace["exact"])
            identities.append((trace["case"], trace["policy"], str(trace["version"]), tuple(trace["disabled"])))
        policy_totals = {}
        for policy in sorted({r["policy"] for r in summary}):
            sample = [r for r in summary if r["policy"] == policy]
            policy_totals[policy] = dict(
                exact=sum(int(r["exact"]) for r in sample),
                requests=sum(int(r["requests"]) for r in sample),
                cases=len(sample),
                complete_cases=sum(r["exact"] == r["requests"] for r in sample),
                mean_case_coverage=statistics.mean(int(r["exact"]) / int(r["requests"]) for r in sample),
                retained_bytes_min=min(int(r["retained_bytes"]) for r in sample),
                retained_bytes_max=max(int(r["retained_bytes"]) for r in sample))
        checks = dict(
            trace_rows=len(traces), exact_trace_rows=sum(t["exact"] for t in traces),
            report_requests_match=len(traces) == report["requests"],
            report_exact_match=sum(t["exact"] for t in traces) == report["exact"],
            unique_request_identities=len(identities) == len(set(identities)),
            every_summary_row_matches_raw=all(grouped[r["case"], r["policy"]] == [int(r["requests"]), int(r["exact"])] for r in summary),
            all_capture_archives_absent=all(t["capture_archive_absent"] for t in traces),
            all_timestamps_ordered=all(t["end_timestamp_ns"] >= t["start_timestamp_ns"] for t in traces),
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            report_raw_hash_present="trace_sha256" in report,
            report_raw_hash_matches=hashlib.sha256(raw).hexdigest() == report.get("trace_sha256") if "trace_sha256" in report else None,
            policy_totals=policy_totals,
            captured_histories=report.get("histories", report.get("captured_histories")),
            planning_cases=report["planning_cases"])
        if group == "tabular":
            robust = [r for r in summary if r["policy"] == "robust"]
            savings = [float(r["saving_vs_snapshots"]) for r in robust]
            by_history = defaultdict(list)
            for r in robust:
                by_history[(r["dataset"], r["estimator"], r["seed"], r["format"])].append(float(r["saving_vs_snapshots"]))
            history_means = [statistics.mean(v) for v in by_history.values()]
            checks["storage_saving_percent"] = dict(
                cases=len(savings), mean=statistics.mean(savings), median=statistics.median(savings),
                minimum=min(savings), maximum=max(savings), zero_saving_cases=sum(v == 0 for v in savings),
                aggregate_case_bytes_saving=100 * (1 - sum(int(r["retained_bytes"]) for r in robust)
                    / sum(int(r["snapshot_bytes"]) for r in robust)),
                strata=[dict(format=fmt, k=k, cases=len(sample), mean=statistics.mean(sample),
                    median=statistics.median(sample), zero_saving_cases=sum(v == 0 for v in sample))
                    for fmt in ("npy", "csv6") for k in (1, 2)
                    for sample in [[float(r["saving_vs_snapshots"]) for r in robust
                        if r["format"] == fmt and int(r["k"]) == k]]],
                captured_histories=len(by_history), history_mean_median=statistics.median(history_means),
                matched_dataset_seed_blocks=len({(r["dataset"], r["seed"]) for r in robust}),
                scope="Fixed datasets and selected split seeds; format and k cases are repeated measurements")
        output[group] = checks
    for group in ("fault_scope", "merged", "components"):
        folder = base / group
        traces = json.loads(gzip.decompress((folder / "execution_traces.json.gz").read_bytes()))
        report = read_json(folder / "report.json")
        output[group] = dict(trace_rows=len(traces), exact_trace_rows=sum(t["exact"] for t in traces),
                             all_capture_archives_absent=all(t["capture_archive_absent"] for t in traces),
                             declared_rows=report.get("exact_requests", report.get("exact_disk_requests")))
    fault_rows = rows(base / "fault_scope/summary.csv")
    output["negative_results"] = dict(
        tabular_zero_saving_cases=output["tabular"]["storage_saving_percent"]["zero_saving_cases"],
        full_fault_scope_saving_percent=sorted({float(r["saving_vs_snapshots"]) for r in fault_rows
            if r["policy"] == "decomposed" and r["scope"] == "with_training_prediction"}),
        qualification="Broader fitting and prediction outages eliminate the storage saving in the captured controls")
    scaling = rows(base / "scaling/summary.csv")
    timing = []
    for groups in sorted({int(r["groups"]) for r in scaling}):
        for k in (1, 2):
            medians = {p: statistics.median(float(r["elapsed_s"]) for r in scaling
                        if int(r["groups"]) == groups and int(r["k"]) == k and r["policy"] == p)
                       for p in ("counterexample", "expanded_exact")}
            timing.append(dict(groups=groups, k=k, **medians,
                               expanded_over_counterexample=medians["expanded_exact"] / medians["counterexample"]))
    output["planner_timing_descriptive"] = timing
    # Keep historical analysis untouched and report the repeated seed structure.
    frontier = rows(root / "results/milestone2/frontier_scaling_oct10/history_medians.csv")
    blocks = defaultdict(list)
    for row in frontier:
        blocks[row["case_id"].rsplit("-rep", 1)[1]].append(float(row["v2_to_v4_speedup"]))
    keys = sorted(blocks)
    estimates = sorted(statistics.median([v for key in sample for v in blocks[key]])
                       for sample in itertools.product(keys, repeat=len(keys)))
    def quantile(values, fraction):
        position = (len(values) - 1) * fraction
        low = int(position)
        high = min(low + 1, len(values) - 1)
        return values[low] + (position - low) * (values[high] - values[low])
    output["historical_frontier_seed_block_correction"] = dict(
        recorded_depth_seed_summaries=len(frontier), independent_seed_blocks=len(blocks),
        depth_counts_per_block={k: len(v) for k, v in blocks.items()},
        median_speedup=statistics.median(float(r["v2_to_v4_speedup"]) for r in frontier),
        exact_seed_block_bootstrap_resamples=len(estimates),
        descriptive_percentile_95=[quantile(estimates, .025), quantile(estimates, .975)],
        scope="Exploratory uncertainty conditional on these three seeds and five fixed depths; too few blocks for a strong population confidence claim",
        historical_issue="Original summary labels 15 depth-seed cases independent and resamples them separately; original files are preserved")
    return output


def regenerate_figures(root):
    comparisons = []
    with tempfile.TemporaryDirectory(prefix="recoverml_evidence_plot_audit_") as temp:
        for script, group in (("analyze_paper_benchmarks.py", "analysis"),
                              ("analyze_retention_extensions.py", "extension_analysis")):
            output = Path(temp) / group
            process = subprocess.run([sys.executable, str(root / "scripts" / script),
                "--input", str(root / "results/research/paper_oct14"), "--output", str(output)],
                cwd=root, text=True, capture_output=True, timeout=180)
            if process.returncode:
                comparisons.append(dict(group=group, returncode=process.returncode,
                                        stdout=process.stdout, stderr=process.stderr))
                continue
            for original in sorted((root / "results/research/paper_oct14" / group).iterdir()):
                if not original.is_file():
                    continue
                generated = output / original.name
                comparison = dict(path=relative(original, root), generated=generated.exists())
                if generated.exists():
                    comparison.update(original_sha256=sha(original), regenerated_sha256=sha(generated),
                                      bytes_identical=original.read_bytes() == generated.read_bytes())
                    if original.suffix == ".json":
                        comparison["json_semantically_identical"] = read_json(original) == read_json(generated)
                comparisons.append(comparison)
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerate-figures", action="store_true")
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    root = args.root.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines())
    by_hash, sources, historical_sources = source_catalogue(root, tracked)
    index_path = root / "results/research/paper_oct14/evidence_inventory.json"
    archive_index = read_json(index_path)
    archive_runs = {str(root / v["source_run"]): k for k, v in archive_index.items()}
    inventory = []
    directories = experiment_directories(root)
    # Earlier working copies may predate the centralized paper archive index.
    # Require two identical evidence files instead of inferring identity by name.
    for directory in directories:
        if "/results/runs/" not in str(directory):
            continue
        for published in directories:
            if "/results/runs/" in str(published):
                continue
            common = [n for n in ("summary.csv", "report.json", "provenance.json")
                      if (directory / n).is_file() and (published / n).is_file()
                      and sha(directory / n) == sha(published / n)]
            if len(common) >= 2:
                archive_runs.setdefault(str(directory), relative(published, root))
                break
    for directory in directories:
        files = [p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        records = {}
        for name in ("report.json", "summary.json", "audit.json", "findings.json", "config.json", "provenance.json", "environment.json"):
            if (directory / name).exists():
                records[name] = read_json(directory / name)
        scalar = {name: {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool))}
                  for name, data in records.items() if isinstance(data, dict)}
        provenance = {}
        report = records.get("report.json", records.get("provenance.json", {}))
        if isinstance(report, dict):
            identities = {"main_generator": report["source_sha256"]} if "source_sha256" in report else {}
            if isinstance(report.get("source_sha256"), dict):
                identities = report["source_sha256"].copy()
            identities.update(report.get("source_dependencies", {}))
            for name, identity in report.items():
                if name.endswith("_sha256") and isinstance(identity, str) and name in (
                        "witness_source_sha256", "optimizer_sha256", "witness_sha256", "planner_sha256",
                        "component_source_sha256", "selector_sha256"):
                    identities[name] = identity
            provenance = {name: dict(sha256=identity, matching_files=by_hash.get(identity, [])) for name, identity in identities.items()}
        category, explanation = classify(directory, files, records, archive_runs)
        inventory.append(dict(path=relative(directory, root), classification=category, rationale=explanation,
            files=len(files), tracked_files=sum(relative(p, root) in tracked for p in files),
            run_complete_marker=(directory / "RUN_COMPLETE").exists(),
            archived_as=archive_runs.get(str(directory)), scalar_reports=scalar, recorded_source_identities=provenance,
            evidence_files={p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file() and
                (p.suffix in (".json", ".csv", ".txt") or p.name == "RUN_COMPLETE")}))
    checksums = {}
    for name in ("CHECKSUMS.json", "CHECKSUMS_GITHUB.json"):
        entries = read_json(root / name)
        missing = [p for p in entries if not (root / p).is_file()]
        changed = [p for p, identity in entries.items() if (root / p).is_file() and sha(root / p) != identity]
        checksums[name] = dict(entries=len(entries), missing=missing, changed=changed)
    result = dict(generated_at=datetime.now(timezone.utc).isoformat(), scan_started_at=started,
        audit_source_sha256=sha(Path(__file__)),
        local_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        scope="Read-only saved-evidence audit including ignored local working directories when present",
        selection_history="No complete prospective experiment registry existed; directory inventory cannot prove absence of deleted or external runs",
        statistical_units="Histories are grouped by dataset and split seed. Formats and k bounds and versions and fault scenarios and timing repeats are repeated measures, not independent sample sizes",
        source_catalogue=sources, historical_source_objects=historical_sources,
        experiments=inventory, headlines=headline_audit(root), checksums=checksums,
        source_snapshot_missing=[dict(experiment=e["path"], dependency=n, sha256=v["sha256"])
            for e in inventory for n, v in e["recorded_source_identities"].items() if not v["matching_files"]],
        generating_programs=[s for s in sources if s["executable_entrypoint"] and not s["source_snapshot"]],
        shell_runners={relative(p, root): sha(p) for p in sorted(root.rglob("*.sh"))
                       if ".git" not in p.parts},
        reproducibility=dict(requirements_sha256=sha(root / "requirements.txt"),
            pyproject_sha256=sha(root / "pyproject.toml"), guide_sha256=sha(root / "reproducibility.txt"),
            workflow_sha256=sha(root / ".github/workflows/tests.yml"),
            clean_install_evidence="results/validation/2026-10-14/reproduction_guide",
            second_physical_machine=False, github_actions_success="Not independently observed by this read-only audit"))
    result["figure_regeneration"] = regenerate_figures(root) if args.regenerate_figures else "Not requested in this invocation"
    ci_path = root / "results/validation/2026-10-15/scientific_audit/github_ci_oct14.json"
    if ci_path.exists():
        ci = read_json(ci_path)
        result["reproducibility"]["github_actions_success"] = dict(
            evidence_path=relative(ci_path, root),
            recorded_runs=[{key: run.get(key) for key in
                ("id", "head_branch", "head_sha", "status", "conclusion", "html_url")}
                for run in ci.get("workflow_runs", [])],
            scope="Observed runs for the recorded October14 commit; later uncommitted audit changes are not covered")
    result["scan_completed_at"] = datetime.now(timezone.utc).isoformat()
    (args.output / "inventory.json").write_text(json.dumps(result, indent=2) + "\n")
    h = result["headlines"]
    s = h["tabular"]["storage_saving_percent"]
    lines = ["# Scientific evidence inventory", "", "Generated by scripts/scientific_inventory.py from saved files without changing old evidence.", "",
        "This is an inventory of files currently present and cannot reconstruct an unrecorded selection process or prove that no other run existed.", "",
        "## Verified headline denominators", "", "| Study | Captures | Cases | Raw requests | Robust exact |", "|---|---:|---:|---:|---:|"]
    for group, policy in (("tabular", "robust"), ("estimators", "robust"), ("published", "RecoverML_decomposed")):
        d = h[group]; p = d["policy_totals"][policy]
        lines.append(f"| {group} | {d['captured_histories']} | {d['planning_cases']} | {d['trace_rows']} | {p['exact']}/{p['requests']} |")
    lines += ["", f"Tabular unweighted case saving mean {s['mean']:.8f}% and median {s['median']:.8f}% and range {s['minimum']:.8f}–{s['maximum']:.8f}% with {s['zero_saving_cases']} zero-saving cases. The ratio of aggregate case bytes gives {s['aggregate_case_bytes_saving']:.8f}% saving and is a different aggregation.",
        "The 48 cases are repeated k-bound evaluations of 24 captures and the two formats share the same dataset and seed, leaving 12 matched dataset–seed blocks. These numbers describe this matrix and are not population estimates.", "",
        "All raw rows match the per-case and per-policy summary counts and request identities are unique in the three primary matrices. All stored trace capture archives are absent. These checks are consistency checks rather than a new execution of recovery.", "",
        "## Preserved negative and conditional evidence", "",
        "- Broader fitting and prediction loss controls have zero saving against snapshots in every recorded model and bound case.",
        "- The initial neural serialization exception is retained in paper_oct14/diagnostics/paper_estimators_oct14.log and the corrected canonical inference artifact is a separate run.",
        "- The strict-capacity protocol pilot is separate from the final normalized-budget comparison.",
        "- Counterexample optimization is slower than expansion in the 6-group k=1 and k=2 and 12-group k=1 scaling settings; speedup is conditional.",
        "- The mixed 112-version graph is one graph and its 112 versions are not independent workflow samples.",
        "- Incomplete and unresolved local working directories appear in the inventory below; missing terminal errors are not replaced with invented explanations.", "",
        "The historical frontier study reused three split seeds across five depths. Its original summary calls all 15 depth–seed cases independent and its unclustered p-value and interval should be treated as exploratory. This audit leaves those files intact and reports a separate whole-seed resampling calculation in inventory.json. Three blocks do not support a strong population confidence claim.", "",
        "## Existing reproduction evidence and remaining checks", "",
        "Pinned direct dependencies and a complete guide and hash manifests exist. The recorded same-host isolated install passed 72 tests with five optional PyTorch skips and regenerated nine figures. This is separate from the earlier 49-test PyTorch validation and the new 100-test CPU PyTorch validation. The GitHub receipt records successful October14 runs while full second-machine paper reproduction and CI for later audit changes remain separate checks.", "",
        "## Experiment directory inventory", "", "| Directory | Classification | Tracked / present files |", "|---|---|---:|"]
    lines += [f"| `{e['path']}` | {e['classification']} | {e['tracked_files']} / {e['files']} |" for e in inventory]
    lines += ["", "Every record in inventory.json includes available completion evidence and immediate report hashes and matching generator/source snapshot identities.",
              "The source catalogue includes every current src module and script and every saved source snapshot and historical_source_objects records sources recovered read-only from local Git history. Remote reachability of each historical object is a separate check. A module's presence alone does not prove that a particular historical experiment executed it.",
              "This inventory is a point-in-time scan while new work may be running. The JSON records its scan start and finish; new incomplete folders are not marked complete by their presence.", ""]
    (args.output / "inventory.md").write_text("\n".join(lines))
    print(json.dumps(dict(experiment_directories=len(inventory), classifications=dict(Counter(e["classification"] for e in inventory)),
        checksum_mismatches={k: len(v["missing"]) + len(v["changed"]) for k, v in checksums.items()},
        unresolved_recorded_source_identities=len(result["source_snapshot_missing"]),
        output=str(args.output)), indent=2))


if __name__ == "__main__":
    main()
