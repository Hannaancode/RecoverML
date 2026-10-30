"""Vector redraw of the author supplied RecoverML architecture image.

The layout, text, and arrow directions follow methodology_user.png. Run from
this directory with ``python make_methodology.py``.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon


BLUE = "#074c7b"
TEXT = "#0d2a4c"
PALE_BLUE = "#eaf5fd"
GOLD = "#997018"
PALE_GOLD = "#fff2cc"


def box(ax, x, y, w, h, label, size=13.0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.012,rounding_size=16",
            linewidth=3.0, edgecolor=BLUE, facecolor=PALE_BLUE,
            zorder=3,
        )
    )
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=size, color=TEXT, linespacing=1.16, zorder=4)


def arrow(ax, points):
    for a, b in zip(points[:-2], points[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=BLUE,
                linewidth=3.0, solid_capstyle="round", zorder=1)
    a, b = points[-2:]
    ax.add_patch(FancyArrowPatch(
        a, b, arrowstyle="-|>", mutation_scale=23,
        linewidth=3.0, color=BLUE, zorder=2,
        shrinkA=0, shrinkB=0,
    ))


def main():
    plt.rcParams.update({"font.family": "DejaVu Serif", "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(11.2, 4.55))
    ax.set_xlim(0, 1968)
    ax.set_ylim(799, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # Arrows are drawn first so that box edges cover their endpoints.
    arrow(ax, [(440, 177), (463, 177), (544, 251)])
    arrow(ax, [(440, 390), (463, 390), (544, 321)])
    arrow(ax, [(928, 288), (978, 288)])
    arrow(ax, [(1222, 265), (1438, 169)])
    arrow(ax, [(1222, 317), (1438, 389)])
    arrow(ax, [(1852, 169), (1917, 169), (1917, 630), (1852, 630)])
    arrow(ax, [(1645, 461), (1645, 556)])
    arrow(ax, [(1438, 633), (1356, 633)])
    arrow(ax, [(987, 633), (906, 633)])
    arrow(ax, [(520, 633), (440, 633)])

    box(ax, 42, 105, 398, 143, "Capture experiment\nfiles + source hashes")
    box(ax, 42, 320, 398, 143, "Declare targets, roots\nand capability losses")
    box(ax, 544, 212, 384, 152, "Physical lineage\nshared blobs paid once", size=12.2)
    ax.add_patch(Polygon([(1108, 186), (1242, 289), (1108, 392), (974, 289)],
                         closed=True, facecolor=PALE_GOLD,
                         edgecolor=GOLD, linewidth=3.0, zorder=3))
    ax.text(1108, 289, "Eligible\nDAG?", ha="center", va="center",
            fontsize=13.5, color=TEXT, linespacing=1.12, zorder=4)
    box(ax, 1438, 100, 414, 138, "Integer minimum cut\nflow + cut certificate")
    box(ax, 1438, 317, 414, 144, "General exact route\nscenario or oracle")
    box(ax, 1438, 556, 414, 153, "Check certificate\nand recovery closure")
    box(ax, 987, 557, 369, 152, "Retain selected\nphysical files")
    box(ax, 520, 556, 386, 154, "Export files or replay\nsurviving producers")
    box(ax, 42, 556, 398, 154, "Verify target SHA-256\nexact output or failure")
    ax.text(1300, 188, "yes", color=TEXT, fontsize=12, ha="center")
    ax.text(1300, 385, "no", color=TEXT, fontsize=12, ha="center")

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(Path(__file__).with_name("methodology_rebuilt.pdf"),
                bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
