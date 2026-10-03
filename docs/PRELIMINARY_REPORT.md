# Milestone 2 — preliminary experimental report

Author: Abdul Hannaan. Experiment date: 3 October 2026.

## Main finding

The prototype works within its stated scope. The coverage-constrained planner produced **775 exact restorations out of 775 admitted version requests**, with **zero unexpected hash mismatches**. It blocked 325 of its 1,100 requests because of required-input budgets or a heuristic inability to fit all protected targets.

This is evidence of tested correctness, not a proof of general correctness, research novelty or broad performance superiority. The principal negative result is important: **saving the requested targets directly matched the proposed policy's storage and restoration behavior in a key opaque-feature workload, with substantially less planning overhead.**

## Experimental design

- 11 workload configurations and 5 independently captured histories each: 55 histories.
- 5 historical versions per history.
- 4 storage budgets: 10%, 25%, 50% and 100% of deduplicated full-snapshot bytes.
- 6 local policy implementations, producing 6,600 uniquely keyed request records.
- Synthetic binary classification at 2,000 and 10,000 rows; native 569-row Wisconsin diagnostic breast-cancer data.
- Logistic regression and 12-tree random forests, fixed seeds, one CPU thread and fixed package versions.
- Hyperparameter edits or contiguous 1% data edits; deterministic pipelines and an intentionally non-replayable external-feature proxy.
- Model and test-set probability arrays protected for every version; one case additionally protects the normalized intermediate matrix.

The external-feature proxy samples an enrichment response with unavailable generator state. It models loss of external information, **not the claim that ordinary seeded scikit-learn training is inherently unreplayable**. Its realizations are captured as artifacts and used identically by every policy within each matched history.

The scaler is fitted only on training rows. Train/test membership is recorded through a seeded split node. No test data are used to fit preprocessing statistics.

## Complete-history results

A history-budget selection counts as complete only when all five version requests succeed exactly and remain within budget. There are 220 selections per policy across all budgets and workloads.

| Policy | Complete history-budget selections | Exact version requests |
|---|---:|---:|
| Full deduplicated snapshots | 55 / 220 | 275 / 1,100 |
| Full replay | 65 / 220 | 325 / 1,100 |
| Cost-ranked cache | 150 / 220 | 780 / 1,100 |
| Pinned non-replayable boundaries + cost cache | 125 / 220 | 625 / 1,100 |
| Direct target snapshots | 135 / 220 | 675 / 1,100 |
| Proposed coverage-constrained planner | **155 / 220** | **775 / 1,100** |

These aggregate counts mix several explicitly documented workloads and infeasible budgets; they are a descriptive summary, not a population estimate. They must not be converted into a universal improvement percentage.

Cost caching restores more individual requests than the proposed method (780 versus 775), but fewer complete histories (150 versus 155). It can preserve only a subset of a history. The proposed policy commits only a selection whose entire protected set remains structurally recoverable. At tight budgets, this all-target requirement can deliberately refuse a set that would restore some individual versions.

All baseline restorations also perform hash verification. We did not disable verification and silently accept incorrect baseline results.

## Controlled opaque-feature example

10,000 rows, logistic regression, parameter-change history, model and prediction targets, five versions and five independent repeats. Full snapshots are evaluated with the 100% budget; other policies below use the 25% budget. This explicitly compares the achievable retained size and feasibility, rather than claiming an equal-budget snapshot speed comparison.

| Policy | Exact requests | Median retained bytes / full snapshot | Median successful restoration |
|---|---:|---:|---:|
| Full snapshots | 25 / 25 | 100% | 0.236 ms |
| Full replay | 0 / 25 | Not successful | Not comparable |
| Pinned boundaries + cost cache | 0 / 25 | Exceeds selected budget | Not executed |
| Direct target snapshots | 25 / 25 | 8.99% | 0.228 ms |
| Proposed planner | 25 / 25 | 8.99% | 0.228 ms |

Both direct target snapshots and the proposed method reduce retained bytes by approximately **91.0%** against the deduplicated full-artifact snapshot reference. The proposed method **does not establish an advantage over direct target snapshots in this example**. The small timing differences are warm-cache measurements with noise and are not evidence of a significant speedup.

Median planning time in this example: approximately 5.34 ms for the proposed method and 0.377 ms for direct target snapshots. Across the whole matrix, median planning time is approximately 5.25 ms versus 0.272 ms. Thus, the planner's overhead is material relative to sub-millisecond artifact loading.

## Cases where direct target snapshots do not fit

At the 25% budget, two deterministic cases restored 25/25 requests with the proposed method while direct target snapshots exceeded the available budget:

- Synthetic 10,000-row logistic-regression parameter histories: proposed median restoration 19.80 ms.
- Public-data random-forest parameter histories: proposed median restoration 17.15 ms.

Cost caching and pinned-boundary caching also restored 25/25 requests in both cases with similar restoration times. These cases show that selective replay can outperform direct snapshots in feasibility, **but do not establish that our particular planner uniquely provides that benefit**.

## Small-instance exact reference

We constructed 18 tiny graph instances with alternative checkpoint paths and three target scopes, then evaluated four budgets per instance: 72 comparisons. The exact solver enumerates all retained subsets. Minimum-feasible-byte selection and minimum-estimated-latency selection under budget are distinct objectives.

Results:

- 18 budgets one byte below the exact minimum were infeasible and were not admitted.
- 54 feasible comparisons were admitted.
- No feasible comparison was rejected in this small suite.
- The heuristic's estimated restoration objective matched the exact optimum in all 54 feasible comparisons; maximum relative objective gap was 0.

This is a result for these small fixtures and the stated cost model. It is **not** evidence that the heuristic is globally optimal on arbitrary DAGs. Larger graphs can have local traps. `heuristic_cannot_fit` is never presented as a proven infeasibility result.

## Correctness verification

14 automated tests cover deterministic replay for both model types, model codec round trips, loaded-model inference, lost external state, corruption before deserialization, execution-environment mismatch, replay parameter mismatch, global invalidation with unchanged-block sharing, unsafe eviction rejection, budget refusal, safe direct-target snapshots, the exact feasibility threshold and cycle detection and recovery of a truncated journal checkpoint.

During development, tests exposed raw random-forest serialization differences from unused node-struct padding. A canonical codec now records numerical/model state and zeros unused padding. Supported models are reconstructed and their predictions are verified against captured prediction hashes. This normalizes non-model bytes; it does not weaken numerical equality to an accuracy tolerance.

Export validation exposed an optional CSV-column error and incomplete per-operation journals. The logger now keeps an in-memory journal and writes atomic checkpoints and a complete final export. To complete the measured traces, 275 requests were re-executed using their original captured artifacts; these new measurements replace the corresponding final rows and are explicitly marked in trace_repairs.json. The original request measurements remain in before_trace_repair_requests.csv. Final audit verifies 6,600 unique requests, 1,320 unique selections and matching per-request restoration-operation counts. Capture trace events are diagnostic records; the restoration-operation trace counts are the audited completeness guarantee. No timings were synthesized.

## Timing and storage accounting

- Restoration time includes dependency traversal, selected-file reads, deserialization/replay, serialization of replayed values and artifact hashing.
- Planning, environment initialization, candidate-store materialization and dataset capture are separately accounted for.
- Planning estimates assume 500 MB/s and 20 microseconds per blob; these are fixed assumptions, not measured device properties.
- Fresh restoration memo state is created per request; the OS page cache is not flushed.
- Budget includes manifest bytes and serialized selected artifact bytes, including all required original input versions.
- Budget excludes diagnostic benchmark logs, optional certificates, filesystem block allocation and the experimental full capture archive.
- `lineage_serialization_s` directly measures graph insertion, serialization and hashing during capture. The remaining non-operator capture time also includes dataset construction and diagnostic work; it is not reported as a clean instrumentation-overhead baseline.

## Research assessment and next implementation priorities

This milestone demonstrates a functioning, auditable implementation of the revised problem. It does **not** justify claiming that the method is now substantially novel or ready for a research publication.

The most informative next experiments are:

1. More diverse branching DAGs with genuinely competing checkpoint alternatives and protected targets at different pipeline stages; compare complete-history feasibility and latency with both boundary pinning and target snapshots.
2. A declared retention/admission policy for an expanding online history, with peak persistent-storage accounting and crash-safe replacement. The current planner is offline.
3. Larger datasets, longer version histories, model-dominated pipelines, scattered record edits and different request distributions.
4. More varied exact-reference graphs to expose heuristic failures and quantify the optimality gap.
5. Lower planner overhead through cached dependency closure and incremental marginal-cost updates, followed by matched end-to-end measurements.

We should prioritize these distinguishing tests rather than add UI features or claim novelty from the existing storage reduction alone.

## Deliverable status

Included: working Python package, explicit supported operators, disk-backed restore CLI, automated benchmark harness, raw CSV/JSONL logs, retention decision traces, certificates, exact-reference fixtures, preliminary plots, correctness tests, pinned dependencies and a complete small captured example.

Pending: instructor-accessible remote Git repository link. No GitHub upload or external publication has occurred.
