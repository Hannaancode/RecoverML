# Final file API scaling and crash evidence (30 October 2026)

The [GitHub Actions run](https://github.com/Hannaancode/RecoverML/actions/runs/41026299655)
completed on source commit `9adf5f0b4cc808b9d5bd046d5eeb90679d5bfc43`.
Its artifact is retained here as `evidence.zip` with SHA-256
`dd905bf76b5dceb5949805af440d453612c57b0fc164462ed673a020b80ffe03`.
The release audit extracts the saved artifact, verifies its byte identity,
checks the source commit and per-file hashes, and recomputes every trial and
request result. Run `PYTHONPATH=src python scripts/audit_runtime_scaling_release.py`.

The audit passed **252 trials and 32,256/32,256 exact requests**. It covers
Breast Cancer with a standard linear recipe and Digits with PCA and neighbors,
each with 1, 4, and 16 versions. Each condition has three repetitions of 128
requests. The final `recover_requested_files` API uses fresh per-request
output directories and the published immutable store. Root-only replay and
retained-target direct export are separate byte-budget modes; they are not
claimed as equal-storage competitors.

Each table value below is the median throughput of three trials. Ratios use
the medians within each fixed dataset, version count and mode. The four-vCPU
GitHub runner reports an AMD EPYC 9V74 CPU. BLAS uses one thread.

| Retention mode | Concurrency sweep | Fixed-case 1-to-high wins | Median high/one throughput ratio | Range |
|---|---|---:|---:|---:|
| Mandatory roots, replay | 1 to 4 same-host processes | 6/6 | 2.50 | 2.05–2.67 |
| Protected target files, direct export | 1 to 4 same-host processes | 6/6 | 1.97 | 1.79–2.14 |
| Mandatory roots, replay | 1 to 8 threads | 0/6 | 0.70 | 0.50–0.94 |
| Protected target files, direct export | 1 to 8 threads | 0/6 | 0.48 | 0.42–0.56 |

The median of each trial's empirical service P99 increases by 1.59 times for
root replay and 3.09 times for direct export at four processes. At eight
threads it increases by 11.75 and 22.38 times, respectively. These are
descriptive tails from 128 requests per trial; the complete request
distribution, including queue wait, is in `requests.jsonl` inside the archive.

At 16 versions, Breast Cancer root replay moves from 88.8 to 210.7 exact
requests/s with four processes, while Digits root replay moves from 46.7 to
124.8. At the same version count, direct export moves from 1597.5 to 2963.7
and from 1191.3 to 2492.1 requests/s. The root-only and direct-export stores
have different measured byte totals, ranging from 150,942 to 975,357 and
from 153,546 to 3,117,275 bytes, respectively. These totals include the
manifest and capability contract.

The process sweep represents concurrent replicas on **one host** sharing one
read-only store. It is an actual same-host capacity measurement, not a
multi-node network test. The earlier prototype's multithread study remains
separately identified in the manuscript. Publication crash checks deliberately
terminate a child immediately before and after atomic rename; before rename
no final store appears, and after rename the final store verifies completely.
The 32-reader check uses isolated outputs. See
`docs/CRASH_CONCURRENCY_PROTOCOL.md` for the exact invariants and scope.
