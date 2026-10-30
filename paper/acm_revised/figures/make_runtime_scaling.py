"""Build the revised paper's scaling chart from the saved raw Action trials."""

from collections import defaultdict
import io
import json
from pathlib import Path
import statistics
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "results/research/runtime_scaling_oct30/evidence.zip"
OUT = Path(__file__).with_name("runtime_scaling.pdf")


def build():
    with zipfile.ZipFile(ARCHIVE) as bundle:
        raw = bundle.read("runtime_scaling_full/trials.jsonl").decode()
    trials = [json.loads(line) for line in raw.splitlines()]
    values = defaultdict(list)
    for row in trials:
        key = (row["dataset"], row["versions"], row["mode"], row["axis"], row["workers"])
        values[key].append(row)
    if len(trials) != 252 or len(values) != 84:
        raise ValueError("Scaling trial matrix differs")
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
                         "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42})
    fig, panels = plt.subplots(2, 2, figsize=(7.0, 2.5), sharex="col")
    colors = {"threads": "#b75b36", "processes": "#12618d"}
    legends = {"threads": "Threads", "processes": "Process replicas"}
    modes = (("root_replay", "Mandatory roots: replay"),
             ("target_files", "Protected target files: direct export"))
    metrics = (("throughput_rps", "Throughput / one worker"),
               ("service_p99_ms", "Service P99 / one worker"))
    for col, (mode, title) in enumerate(modes):
        for row_index, (metric, ylabel) in enumerate(metrics):
            ax = panels[row_index, col]
            for axis, counts, x in (("threads", [1, 2, 4, 8], [0, 1, 2, 3]),
                                    ("processes", [1, 2, 4], [5, 6, 7])):
                medians, low, high = [], [], []
                for count in counts:
                    ratios = []
                    for dataset in ("breast_cancer", "digits"):
                        for versions in (1, 4, 16):
                            key = (dataset, versions, mode, axis, count)
                            reference = (dataset, versions, mode, axis, 1)
                            measured = statistics.median(item[metric] for item in values[key])
                            baseline = statistics.median(item[metric] for item in values[reference])
                            ratios.append(measured / baseline)
                    medians.append(statistics.median(ratios))
                    low.append(min(ratios))
                    high.append(max(ratios))
                ax.plot(x, medians, "o-", color=colors[axis], linewidth=1.5,
                        markersize=3.5, label=legends[axis])
                ax.fill_between(x, low, high, color=colors[axis], alpha=.14, linewidth=0)
            ax.axhline(1, color="#555555", linewidth=.7, linestyle=":")
            ax.axvline(4, color="#b6b6b6", linewidth=.6)
            ax.set_title(title if row_index == 0 else "")
            ax.set_ylabel(ylabel if col == 0 else "")
            ax.grid(axis="y", alpha=.18)
            ax.spines[["top", "right"]].set_visible(False)
            if row_index == 1:
                ax.set_xticks([0, 1, 2, 3, 5, 6, 7],
                              ["T1", "T2", "T4", "T8", "P1", "P2", "P4"])
                ax.set_xlabel("Worker count (T = threads, P = processes)")
            if metric == "service_p99_ms":
                ax.set_yscale("log")
                ax.set_ylim(.8, 32)
            else:
                ax.set_ylim(.25, 3.2)
    panels[0, 0].legend(loc="upper left", frameon=False, fontsize=7)
    fig.tight_layout(pad=.8, w_pad=1.1, h_pad=.8)
    fig.savefig(OUT)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    build()
