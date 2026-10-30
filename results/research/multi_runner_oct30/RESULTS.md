# Independent-runner recovery capacity (30 October 2026)

Seven separate GitHub-hosted Linux jobs completed the synchronized [Action run](https://github.com/Hannaancode/RecoverML/actions/runs/41037831235) from commit `c22da001eb3b88295b23efaabd4a7502dcf4e3da`. The first aggregation job rejected a mistaken assumption that target hashes would be identical across different CPU architectures. Its seven original job artifacts are retained byte-for-byte in `evidence.zip` (SHA-256 in `evidence.sha256`); the corrected release audit checks each runner's saved files, source hashes, request hashes, request timing, and the common workflow shape. Run `PYTHONPATH=src python scripts/audit_multi_runner_release.py`.

Each runner independently captured the same declared Digits/PCA-neighbors 16-version history with seed 20261046, published its own root-only immutable store, warmed the final request, and then answered three timed rounds of 128 historical file requests. The 1-, 2-, and 4-runner scenarios started from the same scheduled UTC epoch. All **2,688/2,688** requests recovered each runner's recorded target bytes exactly. The seven artifacts contain all 21 trial summaries and per-request service times and hashes.

| Independent runners | Median aggregate requests/s (three rounds) | Ratio to one runner | Median efficiency vs sum of individual runner rates |
|---:|---:|---:|---:|
| 1 | 35.22 | 1.00 | 1.00 |
| 2 | 73.26 | 2.08 | 0.93 |
| 4 | 141.05 | 4.00 | 0.80 |

The maximum within-scenario start difference was below 0.00005 seconds. The runners had Haswell and SkylakeX BLAS CPU variants, and their captured target bytes formed two distinct hash sets; the audit checks the same workflow shape and exact recovery against each runner's own target hashes. Ratios describe the provisioned heterogeneous runner set and cannot be read as equal-hardware scaling factors. The experiment measures independent stateless replica capacity. It does not exercise a shared distributed store, network request routing, or distributed crash consistency.
