# Planner efficiency follow-up, 26 October 2026

This engineering change preserves the exact retained-byte objective and declared-loss contract.
It addresses repeated work in the implementation rather than claiming a new optimization algorithm.

## Change and correctness boundary

The component planner builds physical-blob, node-order and protected-target indexes once per call.
Each component projection gathers its own nodes and required roots from those indexes.
All physical aliases and original target ordering are preserved; opaque/root dependency normalization and fallback solver selection are unchanged.
The flow proof checker builds its physical-size lookup once when summing the paid cut, rather than rebuilding it for each retained blob.
It still reconstructs the network independently and checks integer capacities, conservation and equal flow/cut bounds.
The separate grounded recovery check remains enabled.

Indexes are local to the call. There is no cached graph, stale-result reuse, weaker certificate, altered storage accounting or change to model predictions.
Existing exhaustive small-graph tests compare every feasible store and loss with the exact optimum.
A regression case covers physical aliases, repeated/out-of-order targets and nonmutation of input manifests.

## Fixed measurement protocol

The complete protocol is `configs/planner_efficiency_oct26.json`.
The reference source is `3e2cebb00b280e193a698359278a4a33927f19d7`, the current published implementation before this change.
It is loaded from exact Git source bytes in a separate module namespace, sharing only dependencies whose source is unchanged.
Both implementations run in one process under one-thread library limits, with identical frozen graph metadata.
Timed calls include the complete planner API and its checks.
Library warmup is excluded. Each condition has three deterministic randomized-order repetitions.
Independent per-loss closure and frozen optimum reconciliation run outside the timed interval for every measured call.

All 230 published conditions are included: 48 scientific, 72 cloud loss-contract pairs, 108 retinal and two Letter scopes.
Four methods are measured on this full grid: revised RecoverML, previous RecoverML, scenario exact and strong local search.
The 24 metadata-only stress controls cover two analytic topologies, widths 64/256/1024/4096 and seeds 101/211/307.
They compare the previous and revised implementations, rather than making a heuristic scaling claim without running that heuristic.

A small 64-branch prototype was inspected before this protocol; its initial cold-import timing is excluded from the results.
All final conditions and slower outcomes are retained. This is an exploratory engineering follow-up on already observed histories,
not an independently preregistered confirmation or a sample of production workflows.

## Reproduction and durable evidence

Use the pinned Python 3.12 environment and full Git history from `reproducibility.txt`:

```sh
PYTHONPATH=src python scripts/benchmark_planner_efficiency.py --group scientific --output work/fresh_planner_scientific
PYTHONPATH=src python scripts/audit_planner_efficiency.py work/fresh_planner_scientific --output work/fresh_planner_scientific_audit.json
```

Repeat with groups cloud, retinal, letter and scaling, using fresh output directories.
The GitHub workflow `planner-efficiency-oct26.yml` runs every group and uploads raw repetitions, selected sets, protocol,
source identities, progress and audit reports even when a later step fails.
Individual retained sets are content-addressed once and explicitly linked from timing rows.
The original capture archives and published runtime measurements are unchanged.

The complete five-group run and audit are now published in [the results](../results/research/planner_efficiency_oct26/RESULTS.md). All 230 frozen optima are preserved; the largest independent-branch control improves by 7.824x and the wide-frontier control by 1.950x at the median across three seeds. Small frozen groups remain near parity, and every slower case is retained.
A proven optimum cannot be beaten on retained bytes under identical assumptions; the comparison tests the cost of finding and checking it.
Metadata-only evidence does not constitute a new model training or payload-recovery experiment.
