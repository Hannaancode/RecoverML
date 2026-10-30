"""Rebuild the Letter storage figure from the recorded byte totals.

Source: results/research/gigabyte_letter_oct16/analysis.json.
Run from this directory with ``python make_letter_storage.py``.
"""

from pathlib import Path
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SCOPES = json.loads((ROOT / "results/research/gigabyte_letter_oct16/analysis.json").read_bytes())["scopes"]
SNAPSHOT_PRE = np.array([SCOPES["preprocessing"]["snapshot_bytes"],
                         SCOPES["preprocessing"]["gzip_snapshot_bytes"]], dtype=float) / 1_000_000
SNAPSHOT_BROAD = np.array([SCOPES["broad"]["snapshot_bytes"],
                           SCOPES["broad"]["gzip_snapshot_bytes"]], dtype=float) / 1_000_000
RECOVER_PRE = np.array([SCOPES["preprocessing"]["exact_bytes"],
                        SCOPES["preprocessing"]["gzip_exact_bytes"]], dtype=float) / 1_000_000
RECOVER_BROAD = np.array([SCOPES["broad"]["exact_bytes"],
                          SCOPES["broad"]["gzip_exact_bytes"]], dtype=float) / 1_000_000


def make_panel(ax, snapshots, recovered, title):
    centers = np.array([0.0, 1.45])
    width = 0.34
    offset = 0.23
    bars_a = ax.bar(
        centers - offset,
        snapshots,
        width=width,
        color="#96999c",
        label="Target snapshots",
        zorder=3,
    )
    bars_b = ax.bar(
        centers + offset,
        recovered,
        width=width,
        color="#176c9c",
        label="RecoverML",
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_ylim(0.30, 1.4e4)
    ax.set_xlim(-0.55, 2.0)
    ax.set_xticks(centers, ["Canonical", "Canonical + gzip"])
    ax.grid(axis="y", color="#dddddd", linewidth=0.45, zorder=0)
    ax.set_title(title, fontsize=10, pad=7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="both", labelsize=8.5)
    for bars in (bars_a, bars_b):
        for bar in bars:
            value = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.11,
                f"{value:,.2f}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#14263a",
            )
    return bars_a, bars_b


def main():
    plt.rcParams.update({"font.family": "DejaVu Serif", "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.4), sharey=True)
    handles = make_panel(axes[0], SNAPSHOT_PRE, RECOVER_PRE, "(a) Preprocessing loss")
    make_panel(axes[1], SNAPSHOT_BROAD, RECOVER_BROAD, "(b) Broad loss")
    axes[0].set_ylabel("Measured store size (decimal MB, log)", fontsize=9)
    fig.legend(
        [handles[0][0], handles[1][0]],
        ["Target snapshots", "RecoverML"],
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=2,
        frameon=False,
        fontsize=9,
    )
    fig.subplots_adjust(left=0.09, right=0.99, top=0.81, bottom=0.15, wspace=0.13)
    fig.savefig(Path(__file__).with_name("letter_storage.pdf"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
