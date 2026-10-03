# Milestone 2 — second implementation and benchmark iteration

Author: Abdul Hannaan. Experiment date: 3 October 2026. Package version: 0.2.0.

## Main result

The new planner removes much of the first implementation's planning overhead
while preserving its tested recoverability. On 235 matched, fully feasible
history-budget selections, version 2 achieved a **19.3× median paired planning
speedup** and a **3.4× median paired speedup for one planning call plus five
version restorations**, relative to our version 1. Restoration time alone was
essentially unchanged: median paired speedup 0.999×.

Version 2 restored **1,175 / 1,175 admitted requests exactly**, with no hash or
replay failures. It completed **235 / 320** history-budget selections, compared
with **175 / 320** for direct target snapshots. Version 1 also completed 235;
the new version's improvement is lower planning cost and better feasibility
diagnostics, rather than additional observed coverage over version 1.

The strongest simple baselines remain competitive. Where both methods completed
the entire history, direct target snapshots were slightly faster overall:
median baseline/v2 planning-plus-restore ratio 0.984×. Some intermediate-target
cases incurred considerably more search overhead. These measurements establish
a useful improvement to our prototype, **not universal superiority or research
novelty**.

## What changed

Version 1 searches three structural seeds with coverage-constrained reverse
deletion and marginal cache additions. This repeatedly evaluates candidate
sets, even when retaining targets directly already attains the estimated
minimum restore cost.

Version 2 first checks a sufficient lower-bound condition: direct target
artifacts fit the budget, and loading each requested target costs no more than
replaying that target alone, before its dependencies. If this holds, it returns
the direct-target set without a solver. Otherwise a mixed-integer formulation
jointly selects physical blobs and per-version load/replay actions, accounting
for shared ancestors, content deduplication, mandatory source history and
non-replayable operations.

The solver has a 0.5-second solve limit. A returned incumbent is checked against
actual integer-byte storage, structural coverage and the executor's estimated
cost. A valid bounded incumbent is accepted with its gap recorded; a failed
solver would fall back to the original heuristic. Estimated optimality is
reported separately from measured runtime. See `docs/PLANNER_V2.md` for details.

## Experimental design

The final matrix contains **16 cases × 5 independently captured histories × 4
budgets × 7 policies × 5 version requests = 11,200 requests**. It retains all
11 original workload configurations, adds five branching configurations, and
runs both planners on the same newly captured artifacts as all baselines.

Budgets are 10%, 25%, 50% and 100% of the deduplicated full-artifact store,
including metadata and mandatory source history. Model training uses recorded
integer seeds and one CPU thread. Each policy receives identical target scope,
byte budget and external-response realizations within a history. Policy/budget
order is shuffled reproducibly. All blocked and failed requests remain in the
logs; no failed selection is assigned a latency.

| Case | Dataset and model | Boundary | Change | Branches | Additional target |
|---|---|---|---|---:|---|
| 00 | Synthetic 2,000; logistic | Deterministic | Parameters | 1 | — |
| 01 | Synthetic 2,000; logistic | Opaque | Parameters | 1 | — |
| 02 | Synthetic 10,000; logistic | Deterministic | Parameters | 1 | — |
| 03 | Synthetic 10,000; logistic | Opaque | Parameters | 1 | — |
| 04 | Synthetic 10,000; logistic | Deterministic | Data | 1 | — |
| 05 | Synthetic 10,000; logistic | Opaque | Data | 1 | — |
| 06 | Wisconsin 569; logistic | Deterministic | Parameters | 1 | — |
| 07 | Wisconsin 569; logistic | Opaque | Parameters | 1 | — |
| 08 | Wisconsin 569; forest, 12 trees | Deterministic | Parameters | 1 | — |
| 09 | Wisconsin 569; forest, 12 trees | Opaque | Parameters | 1 | — |
| 10 | Synthetic 2,000; logistic | Opaque | Parameters | 1 | Normalized matrix |
| 11 | Synthetic 10,000; logistic | Deterministic | Parameters | 4 | — |
| 12 | Synthetic 10,000; logistic | Opaque | Parameters | 4 | — |
| 13 | Synthetic 2,000; forest, 48 trees | Deterministic | Parameters | 4 | — |
| 14 | Synthetic 2,000; forest, 48 trees | Opaque | Parameters | 4 | — |
| 15 | Synthetic 2,000; logistic | Opaque | Data | 4 | Normalized matrix |

Every case protects every branch's trained model and test-set probability
predictions for each version. Branches share cleaning, train/test membership,
the training-fitted scaler and normalized features. Opaque enrichment is an
external-response proxy with unavailable generator state; ordinary seeded
scikit-learn training remains replayable. Data changes affect a contiguous 1%
of rows. The public dataset remains its native 569 rows. Accuracy is recorded
for context and is never used to weaken restoration equality.

## Coverage across the complete matrix

Each policy has 320 history-budget selections and 1,600 version requests. A
complete selection requires all five requests to succeed exactly within budget.

| Policy | Complete history-budget selections | Exact version requests |
|---|---:|---:|
| Full deduplicated snapshots | 80 / 320 | 400 / 1,600 |
| Full replay | 100 / 320 | 500 / 1,600 |
| Cost-ranked cache | 210 / 320 | 1,099 / 1,600 |
| Pinned boundaries + cost cache | 200 / 320 | 1,000 / 1,600 |
| Direct target snapshots | 175 / 320 | 875 / 1,600 |
| Planner v1 | **235 / 320** | **1,175 / 1,600** |
| Planner v2 | **235 / 320** | **1,175 / 1,600** |

Version 2 completes 60 more history-budget selections than direct snapshots,
25 more than cost caching, and 35 more than boundary pinning. These are counts
in this declared experimental matrix, not general-population improvement rates.
Cost caching sometimes restores only a subset of the history. Every baseline
uses the same artifact verification as the proposed planners.

At the 25% budget, version 2 restores 300 / 400 requests, direct targets
175 / 400 and cost caching 281 / 400. At the 50% budget, version 2 restores
400 / 400, direct targets 275 / 400 and cost caching 353 / 400. At 100%, all
methods except full replay in opaque cases can restore every request.

Of version 2's 425 blocked requests, 225 exceed the mandatory-input-plus-
metadata floor; 200 belong to 40 selections the MILP reports infeasible. These
are distinct from version 1's heuristic failures. No blocked request was timed
as a successful restoration.

## Paired timing results

Ratios below are medians of per-history-budget baseline/v2 ratios. Each pair
uses the same history and budget and requires both methods to restore every
version exactly. Planning is charged once, followed by one measured restore of
each of the five versions. A ratio above 1 favors version 2.

| Baseline | Matched feasible selections | Planning speedup | Restore-only speedup | Planning + five restores speedup |
|---|---:|---:|---:|---:|
| Planner v1 | 235 | **19.281×** | 0.999× | **3.422×** |
| Direct target snapshots | 175 | 0.930× | 1.004× | 0.984× |
| Cost-ranked cache | 210 | 1.048× | 0.996× | 0.997× |
| Pinned boundaries + cost cache | 200 | 0.923× | 1.011× | 0.992× |
| Full snapshots | 80 | 0.931× | 1.002× | 1.001× |
| Full replay | 100 | 0.625× | 28.001× | 24.521× |

Version 2 is faster for planning plus five restores in 210 of the 235 matched
selections against v1. Across each planner's feasible selections, median
planning time is 8.459 ms for v1 and 0.440 ms for v2. These individual medians
are distinct from the median of paired ratios above.

The main negative result persists: simple caching/snapshot baselines have
similar successful restore times and competitive total cost where they fit.
Near-1 ratios do not establish a significant speed difference. The full-replay
comparison is conditional on deterministic cases and suitable budgets; opaque
failures are excluded from latency ratios but retained in coverage statistics.
These preliminary medians are descriptive, without population-level confidence
or significance claims. Budgets from the same captured history are correlated.

The controlled 10,000-row opaque logistic example still retains approximately
8.99% of full-store bytes with either direct targets or v2, a roughly 91% storage
reduction. This storage advantage is shared with the direct-target baseline;
it is not unique to our planner. Full snapshots use the 100% budget in that
reference plot, while the other policies use 25%, as labeled.

## Optimizer diagnostics and correctness

Across 320 v2 selections:

- 45 fail immediately at the mandatory-input storage floor.
- 165 use the direct-target estimated lower-bound shortcut.
- 110 invoke MILP: 69 reach estimated optimality, 40 report infeasibility and
  one returns a valid bounded incumbent at the time limit.
- No fallback was needed in this measured run.

The bounded incumbent occurs in case14-rep2 at the 50% budget. Planning takes
504.8 ms and the recorded model gap is 3.27%. It restores all five versions
exactly, but is not labeled optimal. This outlier demonstrates that median
planning improvements do not imply better tail latency. V1's largest feasible
planning time in the matrix is 84.0 ms.

All **22 automated tests pass**, including supported model replay, inference
after model decoding, corruption/environment/configuration failures, safe
eviction, lost external state, branching pipelines, cycles and journal export.
The new optimizer tests compare 32 small graph/budget cases with exhaustive
enumeration, and exercise solver fallback, bounded incumbents, rejected solver
objectives, shared physical blobs, duplicate and overlapping targets.

The separate tiny pipeline suite compares both planners with exact enumeration
on 18 graphs at four budgets: 144 planner-reference rows. For each planner,
all 54 feasible cases are admitted with zero estimated objective gap, and all
18 infeasible cases are refused. This is a small-instance cost-model check,
not a proof that v1 is globally optimal or that v2 minimizes actual runtime.

The final export audit verifies **11,200 unique declared requests, 2,240 unique
selections, 80 histories and 54,314 trace events**, with every request's load
and replay counts matching its operation trace. This iteration required no
trace-repair re-executions. The original experiment and its explicitly recorded
repairs remain preserved separately.

## Accounting, limitations and research interpretation

Restore time includes reads, deserialization/replay and artifact verification.
The paired cost adds planning but excludes initial environment verification,
store copying and full-history capture. It is therefore not total application
wall time. Memoization is fresh per request; the OS cache is warm. Model
exactness means the defined canonical serialized numerical artifact identity,
not arbitrary process-memory or stock-pickle byte identity.

The estimate assumes 20 microseconds per read plus 500 MB/s and recorded
operation compute times. It does not fully model decoding, replay serialization
and hashing costs. This explains why estimated optimality cannot be equated
with actual runtime optimality. Better independently calibrated costs and
search-overhead-aware stopping are useful next steps.

The byte budget counts selected serialized payloads, metadata and required
source history. It excludes filesystem block allocation, diagnostics and the
experimental complete capture archive. Planning is offline and starts from
fully captured candidates; it does not provide crash-safe online admission or
bounded peak capture storage. Operators and dependencies are declared manually.

Global reuse/materialization optimization is established prior work, including
[HELIX](https://www.vldb.org/pvldb/vol12/p446-xin.pdf). The solver uses the
[SciPy MILP/HiGHS API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).
The implemented shortcut and solver improve our engineering baseline, but do
not establish substantial research novelty. No published system was executed
as a benchmark. Our evidence supports a working, auditable Milestone 2
prototype with lower planning overhead and explicitly constrained recovery.

## Reproduce and submit

Use Python 3.12 and the pinned dependencies. `make test` runs correctness checks;
`make smoke` creates a small fresh run; `make iteration2` runs the full matrix,
audit, plots, paired comparisons and both exact-reference comparisons. Existing
output directories must be renamed or a new output path selected.

Raw measurements and four plots are under `results/iteration2`; the paired
CSV and solver decision logs provide the evidence behind this report. The
complete small captured example can be selected and restored through the CLI.
Full benchmark capture archives are excluded from the compact package and can
be regenerated locally. Opaque responses regenerated on a fresh run have new
hashes, but are shared identically across its policies.

The source, harness, raw traces, plots, reports and tests are published in the
instructor-accessible repository listed in `docs/SUBMISSION.md`. See that guide
for the publication and reproduction checks.
