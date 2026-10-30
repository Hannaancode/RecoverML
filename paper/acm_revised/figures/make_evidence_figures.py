"""Regenerate four historical charts from saved ledgers.

Run scripts/audit_paper_figure_sources.py first to reconcile summarized plot
inputs with their retained planner, store and trial records.
"""

import argparse
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]
BLUE, RUST, GREEN = "#176c9c", "#c76535", "#43845d"


def rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def finish(fig, path):
    fig.tight_layout(pad=.65, w_pad=.9)
    fig.savefig(path)
    plt.close(fig)


def shared_storage(output):
    base = ROOT / "results/research/strong_baseline_cloud_oct16"
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.35), sharey=True)
    categories = [(dataset, versions) for dataset in ("wine", "breast_cancer")
                  for versions in (4, 16, 64)]
    count = 0
    for seed_index, seed in enumerate((20261016, 20261017, 20261018)):
        ledger = rows(base / f"seed{seed}/shared/summary.csv")
        by_history = defaultdict(dict)
        for item in ledger:
            by_history[item["history"]][item["method"]] = item
        for methods in by_history.values():
            exact = methods["RecoverML_exact"]
            local = methods["robust_local"]
            dataset, versions = exact["dataset"], int(exact["versions"])
            concat = exact["concat_materialized"] == "True"
            x = categories.index((dataset, versions)) + (seed_index - 1) * .075
            saving = 100 * (int(local["retained_bytes"]) - int(exact["retained_bytes"])) / int(local["retained_bytes"])
            axes[int(concat)].scatter(x, saving, s=13, marker="o" if dataset == "wine" else "s",
                                      color=BLUE if dataset == "wine" else RUST, linewidths=0)
            count += 1
    if count != 36:
        raise ValueError("Shared-loss figure needs 36 fixed histories")
    for ax, title in zip(axes, ("(a) Fused views: 18 cases", "(b) Stored concat: 18 controls")):
        ax.axhline(0, color="#444", linewidth=.7)
        ax.set_xticks(range(6), ["W4", "W16", "W64", "B4", "B16", "B64"])
        ax.set_ylim(-2, 53)
        ax.set_title(title)
        ax.grid(axis="y", alpha=.15)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Storage reduction vs local search (%)")
    axes[0].set_xlabel("Dataset and number of versions")
    axes[1].set_xlabel("Dataset and number of versions")
    finish(fig, output / "shared_storage.pdf")


def planner_timing(output):
    path = ROOT / "results/research/strong_baseline_cloud_oct16/seed20261016/dag_timing/report.json"
    evidence = json.loads(path.read_bytes())["results"]
    if len(evidence) != 48 or sum(bool(item["dag_eligible"]) for item in evidence) != 36:
        raise ValueError("Planner timing grid differs")
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.3), sharey=True)
    for panel, (field, title) in enumerate((("speedup_vs_local", "(a) Versus strong local"),
                                            ("speedup_vs_scenario", "(b) Versus scenario exact"))):
        ax = axes[panel]
        for group, color in ((True, BLUE), (False, RUST)):
            items = [item for item in evidence if bool(item["dag_eligible"]) == group]
            values = [float(item[field]) for item in items]
            x0 = 0 if group else 1
            xs = [x0 + ((index * 17) % 23 - 11) / 95 for index in range(len(items))]
            ax.scatter(xs, values, s=13, color=color, linewidths=0)
            median = statistics.median(values)
            ax.plot([x0 - .19, x0 + .19], [median, median], color="#222", linewidth=1)
            ax.text(x0 + .22, median, f"{median:.2f}x", va="center", fontsize=6)
        ax.axhline(1, color="#555", linestyle="--", linewidth=.7)
        ax.set_yscale("log")
        ax.set_ylim(.2, 60)
        ax.set_xticks([0, 1], ["DAG (36)", "Fallback (12)"])
        ax.set_title(title)
        ax.grid(axis="y", alpha=.15)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Baseline / RecoverML planning time")
    finish(fig, output / "planner_timing.pdf")


def native_recovery(output):
    base = ROOT / "results/research/native_frontier_cloud_oct16/v4"
    raw = []
    for seed in (20261016, 20261017, 20261018):
        path = base / f"seed{seed}/native_paired/raw_recovery.jsonl"
        raw.extend(json.loads(line) for line in path.read_text().splitlines())
    if len(raw) != 216:
        raise ValueError("Native recovery trial matrix differs")
    grouped = defaultdict(list)
    for item in raw:
        grouped[(item["history"], item["method"])].append(item)
    points = []
    for history in sorted({item["history"] for item in raw}):
        r = grouped[(history, "RecoverML_native")]
        d = grouped[(history, "DVC_native_batch")]
        if len(r) != 3 or len(d) != 3:
            raise ValueError("Native paired repetitions differ")
        rm = statistics.median(item["elapsed_s"] for item in r)
        dm = statistics.median(item["elapsed_s"] for item in d)
        points.append((dm, rm, dm / rm, r[0]["downstream_targets"] == 0))
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.55))
    for dm, rm, ratio, retained in points:
        color = RUST if retained else BLUE
        marker = "s" if retained else "o"
        axes[0].scatter(dm, rm, color=color, marker=marker, s=14, linewidths=0)
    axes[0].plot([.04, 3], [.04, 3], linestyle="--", color="#777", linewidth=.7)
    axes[0].set(xscale="log", yscale="log", xlabel="Native DVC median elapsed time (s)",
                ylabel="RecoverML median elapsed time (s)", title="(a) All 36 paired histories")
    for group, x, color, marker in ((False, 0, BLUE, "o"), (True, 1, RUST, "s")):
        ratios = [p[2] for p in points if p[3] == group]
        for index, ratio in enumerate(ratios):
            axes[1].scatter(x + ((index * 11) % 17 - 8) / 90, ratio,
                            color=color, marker=marker, s=14, linewidths=0)
        median = statistics.median(ratios)
        axes[1].plot([x - .2, x + .2], [median, median], color="#222", linewidth=1)
        axes[1].text(x + .22, median, f"{median:.2f}x", va="center", fontsize=6)
    axes[1].axhline(1, color="#777", linestyle="--", linewidth=.7)
    axes[1].set(xticks=[0, 1], xticklabels=["Replay required", "Targets retained"],
                ylabel="Native DVC / RecoverML time ratio", title="(b) Ratios of per-history medians")
    for ax in axes:
        ax.grid(axis="y", alpha=.15)
        ax.spines[["top", "right"]].set_visible(False)
    finish(fig, output / "native_recovery.pdf")


def retinal_storage(output):
    data = rows(ROOT / "results/research/eyeai_complete_oct15/summary.csv")
    by_case = defaultdict(dict)
    for item in data:
        key = (item["estimator"], item["seed"], item["versions"],
               item["target_mode"], item["availability"])
        by_case[key][item["policy"]] = item
    if len(by_case) != 108:
        raise ValueError("Retinal storage conditions differ")
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.3), sharey=True)
    colors = {"intact": BLUE, "legacy_removed": RUST,
              "training_prediction_removed": GREEN}
    labels = {"intact": "Intact", "legacy_removed": "Legacy extractor lost",
              "training_prediction_removed": "Training + prediction lost"}
    for key, methods in by_case.items():
        estimator, seed, versions, target_mode, availability = key
        exact = int(methods["RecoverML_exact"]["retained_bytes"])
        snapshot = int(methods["DVC_target_snapshots"]["retained_bytes"])
        saving = 100 * (snapshot - exact) / snapshot
        x = ((2, 8, 16).index(int(versions)) + (int(seed) - 2) * .027 +
             (-.075 if estimator == "logistic" else .075))
        ax = axes[0 if target_mode == "model_prediction" else 1]
        ax.scatter(x, saving, s=17, color=colors[availability],
                   marker="o" if estimator == "logistic" else "^", linewidths=0)
    for ax, title in zip(axes, ("(a) Model + prediction targets", "(b) Targets also include features")):
        ax.set_title(title)
        ax.set_xticks([0, 1, 2], ["2", "8", "16"])
        ax.set_ylim(-3, 101)
        ax.set_xlabel("Historical versions")
        ax.grid(axis="y", alpha=.15)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Storage saved vs target snapshots (%)")
    handles = [plt.Line2D([], [], marker="o", linestyle="None", color=color,
                          label=labels[name], markersize=5)
               for name, color in colors.items()]
    axes[1].legend(handles=handles, frameon=False, fontsize=6, loc="lower right")
    finish(fig, output / "retinal_storage.pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 7, "axes.titlesize": 8,
                         "axes.labelsize": 7, "xtick.labelsize": 6.5,
                         "ytick.labelsize": 6.5, "pdf.fonttype": 42})
    shared_storage(args.output)
    planner_timing(args.output)
    native_recovery(args.output)
    retinal_storage(args.output)
    print("Regenerated four historical vector charts from saved plot ledgers")


if __name__ == "__main__":
    main()
