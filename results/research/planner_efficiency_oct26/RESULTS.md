# Complete planner efficiency follow-up, 26 October 2026

Runtime source: `296f1266593243fe3de923b6f38aa761aa599e6c`.
Reference implementation: `3e2cebb00b280e193a698359278a4a33927f19d7`.
[GitHub Actions run 40286111028](https://github.com/Hannaancode/RecoverML/actions/runs/40286111028) completed and audited all five groups.
The local complete-release checker also passes for all five original artifact ZIPs and all 30 members.
It reconciles **230 frozen conditions, 24 scaling controls, 2,904 timed calls and 9,096 declared-loss closure checks**.
All revised/previous/scenario exact calls retain the frozen optimum. This study measures metadata planning, not new model recovery.

## What improved

At 4,096 independent branches (12,289 graph nodes), the revised planner is **7.824x faster at the median across three seeds**.
Per-history median times are 1.37-1.42 seconds revised versus 10.72-10.85 seconds previous.
For a 4,096-wide retained frontier (4,098 nodes), the median paired speedup is **1.950x**.
Across the complete 24-control stress grid, the revised implementation is faster in 22 and slower in two, with a 1.442x median paired ratio.
These controls have analytical optima and no model payloads. They do not represent production-workload prevalence.

The change indexes component nodes/targets once per call and avoids rebuilding the physical-size map for every paid vertex in a proof.
The same independent flow/cut and grounded recovery checks remain enabled. There is no persisted planner cache.
This is an implementation scaling improvement using established optimization methods.

| Width | Independent-branch median speedup | Wide-frontier median speedup |
|---|---:|---:|
| 64 | 1.100x | 0.984x |
| 256 | 1.445x | 1.135x |
| 1024 | 2.337x | 1.243x |
| 4096 | 7.824x | 1.950x |

Each cell above is the median of three per-history ratios; each history uses three randomized-order repetitions per method.
The full protocol was fixed before running these grids, after a disclosed small prototype.
The [figure](comparison.png) includes all controls and frozen-history slowdowns.

## Frozen histories: mostly parity with the previous implementation

| Group | Conditions | Median previous/revised time | Revised faster / slower | Median local/revised time | Median scenario/revised time |
|---|---:|---:|---:|---:|---:|
| Scientific | 48 | 1.0007x | 24 / 24 | 4.07x | 2.45x |
| Cloud | 72 | 0.9954x | 30 / 42 | 10.77x | 1.62x |
| Retinal | 108 | 0.9958x | 46 / 62 | 3.17x | 1.43x |
| Letter | 2 | 1.0047x | 1 / 1 | 82.66x | 2.64x |

The revision is faster than strong local search in **212/230** conditions and scenario exact in **217/230**.
Both have faster cases, which remain in the data.
Against the previous implementation, 101 conditions are faster and 129 slower; group medians remain close to one.
Do not interpret the synthetic scaling gain as a uniform gain on these small captured graphs.

The worst previous/revised ratio is 0.2838 for shared Wine seed 20261016, 64 versions, fused views:
the revised median is 50.17 ms versus 14.24 ms previous (about 3.52x slower).
Its three revised timings are 50.17, 14.61 and 51.96 ms, all retained.
No cause or statistical significance is established, and the outlier is not removed.
The revised implementation still beats local search there, but is also slower than scenario exact.

In the cloud group, the revised planner is faster than local search in 72/72 conditions.
Median paired local/revised ratios are 10.77x for separate losses and 15.13x for shared loss.
There are six small serialization storage gaps in separate loss and nine larger gaps in shared loss, reproducing the earlier comparison.
These are the same captured histories and optima, not new independent storage evidence.
Every manual optimal frontier continues to tie exact storage.

## Scope and raw evidence

The four frozen groups cover all previously published scientific (48), cloud (72), retinal (108) and Letter (2) conditions.
Cloud conditions pair two loss contracts on 36 captures; versions, conditions, seeds and requests are not interchangeable independent units.
Each group ran on one GitHub runner; host timing is descriptive.
Four complete planner APIs are timed on the frozen grid. Scaling controls compare only the two RecoverML revisions.
The reference is loaded from unchanged Git source bytes under a separate module namespace, with source-checked shared dependencies.
Library warmup, post-call per-loss closure checks and input reconciliation are outside timing; complete planner checks are inside.
All raw repetitions and adverse outcomes are preserved.

Each group directory retains the original `planner_comparison` files and runner `audit.json`.
`github_artifacts` holds the original ZIPs, and `receipts` identifies their GitHub digests and every extracted member.
[complete_audit.json](complete_audit.json) records cross-group completeness and summaries.
No capture/model payload is loaded, retrained or regenerated here. Earlier native recovery results retain their original source revisions.

## Recheck

Use the pinned environment and full Git history:

```sh
PYTHONPATH=src python scripts/audit_planner_efficiency_release.py results/research/planner_efficiency_oct26 --output work/fresh_complete_planner_audit.json
```

For fresh timings, follow [the protocol](../../../docs/PLANNER_EFFICIENCY_OCT26.md) and use fresh output directories.
A valid retained-byte optimum cannot be beaten under the same accounting and contract.
This follow-up strengthens scalability evidence and does not establish universal dominance or a new optimization theory.
The historical missing Letter archive-container distinction remains unchanged.
