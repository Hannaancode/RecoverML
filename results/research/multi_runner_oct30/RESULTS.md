# Independent-runner recovery capacity (30 October 2026)

Seven separate GitHub-hosted Linux jobs completed the synchronized [successful Action run](https://github.com/Hannaancode/RecoverML/actions/runs/41040344624) from commit `2812e626d634818e6935362741b9c09aecd44f03`. Its aggregated raw Action artifact is retained byte-for-byte in `evidence.zip` (SHA-256 in `evidence.sha256`); the release audit checks each runner's saved files, source hashes, request hashes, request timing, and the common workflow shape. Run `PYTHONPATH=src python scripts/audit_multi_runner_release.py`.

The [earlier run](https://github.com/Hannaancode/RecoverML/actions/runs/41037831235) completed all seven measurements, but its first aggregation job rejected a mistaken assumption that target hashes would be identical across different CPU architectures. Those original runner artifacts are retained in `pilot_evidence.zip`, with their own SHA-256 file. The audit was corrected to require the same declared workload shape and exact recovery against each runner's own captured target hashes, then the complete study was rerun successfully.

Each runner independently captured the same declared Digits/PCA-neighbors 16-version history with seed 20261046, published its own root-only immutable store, warmed the final request, and then answered three timed rounds of 128 historical file requests. The 1-, 2-, and 4-runner scenarios started from the same scheduled UTC epoch. All **2,688/2,688** requests recovered each runner's recorded target bytes exactly. The seven artifacts contain all 21 trial summaries and per-request service times and hashes.

| Independent runners | Median aggregate requests/s (three rounds) | Ratio to one runner | Median efficiency vs sum of individual runner rates |
|---:|---:|---:|---:|
| 1 | 36.43 | 1.00 | 1.00 |
| 2 | 71.36 | 1.96 | 0.83 |
| 4 | 144.69 | 3.97 | 0.82 |

The maximum within-scenario start difference was below 0.00009 seconds. The runners had Haswell and SkylakeX BLAS CPU variants, and their captured target bytes formed two distinct hash sets; the audit checks the same workflow shape and exact recovery against each runner's own target hashes. Ratios describe the provisioned heterogeneous runner set and cannot be read as equal-hardware scaling factors. The experiment measures independent stateless replica capacity. It does not exercise a shared distributed store, network request routing, or distributed crash consistency.
