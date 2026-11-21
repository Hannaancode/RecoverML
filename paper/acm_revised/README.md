# RecoverML manuscript

Open the [final 12-page paper](../../output/pdf/RecoverML_paper_revised.pdf)
or edit [the ACM LaTeX source](RecoverML_paper_revised.tex). The LaTeX source
contains the bibliography and builds in the supplied double-column format.
The class, fonts and seven vector figures are in this directory.

## Rebuild from saved study records

From the repository root, use Python 3.12 and Tectonic 0.17.0 on your PATH:

    python -m pip install .
    python scripts/rebuild_revised_paper.py

The script audits the archived requests and figure inputs, regenerates every
figure, and compiles the paper to output/pdf/RecoverML_paper_revised.pdf.
Install Poppler (pdfinfo) to enable the automated page-count check.
To compile the LaTeX using the existing figure files in Overleaf, select
XeLaTeX and RecoverML_paper_revised.tex as the main file.

The [figure source audit](../../docs/PAPER_FIGURE_SOURCE_AUDIT_OCT30.md)
identifies the saved records behind each plot. Figure 1 is the vector redraw
of the supplied architecture sketch. The Letter figure is regenerated from
saved byte and selection records. The reconstructed frontier payloads match
the recorded hashes and sizes, while the original archive is unavailable.

## Review evidence

The [technical response record](../../docs/reviews/GROUP2_RESPONSES_2026-11-19.txt)
covers the earlier Group 2 revisions.
The [additional measurements](../../results/research/reviewer_m4_m8_nov20)
support the final solver-scaling and compression sections. The M4 CSVs record
the saved general solver measurements. For M8, runs.jsonl holds the timed
phases, summary.json holds medians, and provenance.json records the host and
source identities. The [benchmark script](../../scripts/benchmark_review_compression.py)
records the timing protocol.
