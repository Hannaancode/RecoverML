# Baseline annotation sensitivity

Status: **PASS** and 5760 metadata-only conditions across 8 frozen captures

The pinned HYPPO functions and the tested HELIX rule were run with nonuniform operation-cost changes and declared access weights and eligibility controls. Coverage uses the same captured graphs and fault sets. No model training or disk restoration or recovery timing was performed by this sweep.

| Changed annotation | Paired comparisons | Selected set changes | Exact request-count changes |
|---|---:|---:|---:|
| cost_profile | 4608 | 298 | 139 |
| frequency_profile | 2880 | 312 | 232 |
| eligibility | 2880 | 2190 | 1727 |
| read_MiB_s | 960 | 140 | 32 |
| tie_order | 720 | 180 | 60 |

Zero changes remain part of the result. Changes in access weights are assumptions rather than observed scientific access frequencies. Repeated annotations on one captured graph are correlated controls and do not increase the number of independent workflows. This baseline-only sweep does not establish an optimal partial-coverage bound or native full-system performance.
