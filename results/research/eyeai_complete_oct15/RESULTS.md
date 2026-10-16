# Verified rebuilt EyeAI-inspired retinal study

These are newly executed constructed histories on all 20 STARE images and their Adam Hoover vessel annotations. They are inspired by the published EyeAI processing-revision example and are not a clinical reproduction of EyeAI.

Grid reconciliation: **PASS** with 540 method rows and 10920 actual disk recovery requests and 10920 exact recoveries and 0 unexpected errors.

Native DVC: 624 actual checkout commands. Each output hash was verified. Their receipts are reused across matching availability conditions and are not counted as new native executions.

| Comparison against the certified exact minimum | Conditions |
|---|---:|
| Exact saves bytes against target snapshots | 90 |
| Exact ties target snapshots | 18 |
| Exact beats simple robust greedy | 12 |
| Exact ties simple robust greedy | 96 |
| Exact beats strong local heuristic | 0 |
| Exact ties strong local heuristic | 108 |

Largest absolute target-snapshot saving: **12,316,663 bytes** (95.66%) for forest seed 3 with 16 versions and targets investigation_features under intact.

Savings come from preserving common inputs or an earlier feature frontier and replaying model stages. Snapshot loads can be much faster than retraining. Broad retirement of both training and prediction forces target retention and can remove all target-snapshot savings. A heuristic matching the exact minimum is a tie and is not evidence of an optimization advantage.

The practical question has two parts. These histories show whether selective retention can save storage and whether the particular exact solver improves the decision over the tested strong heuristic. Large artifact count and a large percentage saving do not by themselves establish hard or meaningful optimization choices. The heuristic gap counts above provide the direct test.

The CSV contains planning wall time and process CPU time and P50/P90/P99 recovery latency. Raw JSONL records timestamps and CPU and process I/O counters and operation events and expected and actual SHA-256 hashes. `economics.csv` gives measured CPU-seconds per saved GiB-day break-even ratios for 1/10/100 restores and 1/30/365 retention days. No cloud price is invented.

Timing uses one request repetition on this host with no cold-cache isolation. The three seeds reuse the same 20 images and version counts are nested design settings. These are descriptive results rather than evidence from 108 independent production workflows. Native DVC checkout cost is separate from direct snapshot reads and includes CLI startup. Full native DVC replay is a separate control.
