# Strong baseline follow-up on 16 October

## Completed cloud rerun

The durable three-seed run 38945172079 has now completed. Its full raw evidence
and cross-block audit are at `results/research/strong_baseline_cloud_oct16`.
There are 19,652 actual requests across both loss groupings, with zero unexpected
outcomes. Shared-loss exact storage beats the specified local search in9/36
histories by up to48.7380%, ties27, and ties every manual frontier. All18 concat
controls tie. Median paired planning speedups versus local are11.92/16.88 for
separate/shared losses. These are fresh executions, not the lost original logs.
The historical progress sections below remain as provenance of the interrupted
attempts. Use the new RESULTS.md and complete_audit.json for completed claims.

The earlier studies do not establish that RecoverML beats every other method
Strong local search and manual DVC retention already match several proven storage minima
No method can improve a proven minimum under the same byte accounting and recovery contract

## Engineering change

The exact service now recognizes the single producer physical DAG class described in TRACTABLE_SUBCLASS_OCT15.md
For this class it uses integer minimum cut and checks a feasible flow with an equally priced retained cut
The proof checker uses no optimization solver and rejects changed flow values and invalid capacities and missing or repeated flow edges
Alternative physical producers and physical cycles fall back to the existing general exact engines
Both old measurements and old source snapshots remain unchanged

This is an implementation of established vertex splitting and maximum flow
It is not a new graph algorithm or proof of a new general optimization theory
The primary references are the [MIT flow notes](https://courses.csail.mit.edu/6.854/16/Notes/n9-advanced_flow_algorithms.html) and [NetworkX flow documentation](https://networkx.org/documentation/stable/reference/algorithms/flow.html)

The production engine agrees with brute force on 64 generated DAGs at three loss bounds
Tests include zero byte weights and integer costs above the exact range of binary floating point
The initial complete suite passes 124 tests with six optional Torch tests skipped in the minimal environment

## Fixed new diagnostic study

The protocol is configs/multiview_followup_oct16.json
The public Wine and Breast Cancer datasets are split with three declared seeds
Each history uses 4 or 16 or 64 logistic models across the same fixed regularization range
All input columns are used and every model configuration is retained
Each view fits its StandardScaler on training rows only
The targets are fitted model bytes and held out probability bytes

Each history is captured with two feature inputs consumed inside training and prediction
A second control explicitly captures a common combined feature table
This tests whether a storage advantage depends on the captured stage boundaries
These are deliberately constructed diagnostic workflows and not independent production histories
Wine was used in older project studies so this is not an entirely unseen dataset study

The first grid has separate declared failures for the two preprocessing entrypoints
It completed all 36 histories and 324 method conditions and 972 timed planner calls
There are 12948 actual recovery requests with 10493 exact outcomes and 2455 expected blocked outcomes and zero unexpected outcomes
Identical policy stores share explicitly linked actual measurements and are not counted as separate executions
An independent fixed point audit verifies every request identity and all 108 recorded flow proofs and every captured payload
Duplicate and missing and replacement duplicate request controls are rejected

In this separate entrypoint grid strong local search ties 30 storage conditions and loses six by only 129 bytes
Those six differences are serialization overhead and are not a substantial storage improvement
The manual frontier matches all 36 exact minima
Planning is faster than strong local search in all 36 comparisons with a median descriptive speedup of about 11 times
Some early timings overlap the initial test suite so the later frozen-history timing study is needed for a cleaner planner comparison

## Correlated entrypoint follow-up

The second frozen protocol is configs/multiview_shared_followup_oct16.json
It reuses all original captured bytes and assigns both standardization operations to their shared implementation entrypoint
Retiring that entrypoint disables both views together
All methods receive the same changed contract
The separate entrypoint grid remains unchanged

A disclosed metadata pilot on Wine seed 20261016 with 64 versions found exact storage of 138676 bytes versus 270469 bytes for strong local search
The combined table control tied at 130480 bytes
The pilot motivated a full grid with both datasets and all seeds and sizes and controls
This follow-up is exploratory and was not independently chosen before any pilot result
Its completed results and independent audit will determine the final claim

The nine comparisons include a manual best frontier and the exact scenario formulation
The manual frontier chooses the cheapest feasible whole view frontier or whole target frontier or combined table frontier
HYPPO uses the pinned released materialization component and HELIX uses the documented published rule
Neither is a complete native system lifecycle in this follow-up
The manual frontier is a retention set control and is not a new native DVC run

## Meaning of a successful result

A storage win over local search on this grid would establish a specific failure of one addition exchange under correlated losses
It would not establish a win over every stronger search method or over a correctly hand chosen optimal DVC store
The combined table control can remove the gap and is part of the result
Minimum storage and minimum restoration time are different goals and full snapshots can restore faster
No old result will be removed to create an appearance of universal superiority

The paper and PDF remain unchanged while validation continues

## Durable replay after a session reset

The source and complete separate entrypoint grid were published before the session reset
The first shared entrypoint run completed locally but its closed raw logs were not uploaded before that reset
Its earlier chat counts and timings are therefore not admitted as published execution evidence
The complete shared grid is being replayed as multiview_shared_followup_oct16_rerun1 from the unchanged published captures
The runner now closes one complete gzip member per history and records a checked progress receipt
Compressed prefix checkpoints are published under results/validation/2026-10-16/shared_loss_replay_checkpoints
They are partial execution evidence and do not claim that the full grid has finished
Only the final closed and independently audited replay will supply the completed shared study claims

The local replay was interrupted before its final publication as well
The durable rerun is defined by .github/workflows/strong-baseline-followup.yml
It runs all three fixed seed blocks on separate GitHub runners and makes new captures on each runner before recovery
This preserves the strict recorded runtime contract rather than silently changing the environment of the old captured models
Each block checks both full failure groupings and uploads its raw logs and captures and audits even if a later step fails
These are fresh executions with new timestamps and not reconstructions of the lost local logs

## Final native comparator follow-up

The separate paired native DVC study is complete. Read [its full protocol, final v4 results and preserved baseline corrections](../results/research/native_frontier_cloud_oct16/RESULTS.md) and the [comparator decision](COMPARATOR_DECISION_OCT16.md). The complete cloud storage rerun supersedes the historical interrupted replay status above.
