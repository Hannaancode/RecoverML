# Results guide

Start with milestone2 for the current submission and use archive for the earlier storage studies
Every previously submitted result file is retained and the original experiment data has unchanged bytes
The separate reports and source and configs remain available for future work

| Evidence | Folder |
|---|---|
| Latest throughput and latency experiment | [milestone2/performance](milestone2/performance) |
| Storage smoke check | [milestone2/storage](milestone2/storage) |
| Tests and runner output from that experiment | [milestone2](milestone2) |
| Repeated Digits and Wine study | [milestone2/new_data_oct9](milestone2/new_data_oct9) |
| Planner V3 paired ablation | [milestone2/planner_ablation_oct9](milestone2/planner_ablation_oct9) |
| Planner V4 frontier scaling study | [milestone2/frontier_scaling_oct10](milestone2/frontier_scaling_oct10) |
| CPU neural replay study | [milestone2/neural_oct11](milestone2/neural_oct11) |
| Wide graph topology study | [milestone2/topology_scaling_oct11](milestone2/topology_scaling_oct11) |
| Latest 31 test log and stronger audit check | [validation/2026-10-08](validation/2026-10-08) |
| Original 6600 request storage experiment | [archive/preliminary](archive/preliminary) |
| Expanded 11200 request storage experiment | [archive/iteration2](archive/iteration2) |
| Original correctness and CLI checks | [archive](archive) |

## Current performance evidence

- requests.csv records every request and its UTC and monotonic times and exact outcome
- summary.csv records throughput and request counts and service and response P50 P90 P99
- resources.csv records CPU time and CPU utilization and resident memory
- operations.jsonl.gz contains the complete compressed raw operation log
- captures.json and plans.json record the captured graph and retained artifacts
- config.json and provenance.json record settings and environment and source identities
- HASHES.json checks evidence files and audit.json records the audit result
- throughput_vs_concurrency.png and latency_cdf.png are the preliminary plots
- RUN_COMPLETE records successful completion

See the [performance report](../docs/reports/PERFORMANCE_REPORT.md) for method and findings

## Earlier storage evidence

The archive keeps the original raw_requests.csv and execution_traces.jsonl and retention plans and audits
It also keeps exact reference fixtures and comparison tables and environment records
The preliminary folder retains the original measurements before trace repair and the repair record
The iteration2 folder contains the paired planner comparison and storage coverage plots

- [Storage coverage plot](archive/iteration2/success_by_budget.png)
- [Planning and total cost plot](archive/iteration2/paired_costs.png)
- [Storage and restore time plot](archive/iteration2/opaque_workload.png)
- [Iteration 2 report](../docs/reports/ITERATION2_REPORT.md)
- [Original report](../docs/reports/PRELIMINARY_REPORT.md)

## New data study

Run `make new-data-repeated` to evaluate the real Digits and Wine datasets which were not used in the earlier matrix
The reviewable output is published in [milestone2/new_data_oct9](milestone2/new_data_oct9)
The run uses logistic regression and random forests with deterministic and opaque boundaries and three independent seeds
It contains 24 histories and 3600 requests and 10030 trace events and its complete matrix audit passes
Planner V3 restored all 535 admitted requests exactly and at a 40 percent budget it restored all 120 requests while target snapshots restored 45 and full replay restored 60
Run `make planner-ablation` after the repeated study to reproduce the paired planner timing evidence
The ablation records 900 raw paired trials and shows that version 3 used 98 variables instead of 129 and made the same decision in every trial

## Replayability frontier scaling study

Run `make frontier-scaling` to reproduce the Planner V2 and V3 and V4 scaling comparison on the public Iris dataset
The published output is in [milestone2/frontier_scaling_oct10](milestone2/frontier_scaling_oct10)
It contains 15 captured histories and 1350 timed planner executions and 120 exact restores
All 450 paired planner sets reached proven optima and returned the same objective
At a frontier depth of 128 V4 reduced the formulation from 1256 variables to 69 and the median history level planning speedup over V2 was 3.38 times

## CPU neural replay study

Run `make neural-study` to reproduce the Digits multilayer neural network experiment
The published output is in [milestone2/neural_oct11](milestone2/neural_oct11)
It contains 6 captured histories and 210 policy selections and 630 recovery requests and 1233 raw trace events
Every admitted version 4 request restored exact bytes and the complete matrix audit found no unexpected failures
At a 50 percent budget version 4 restored 18 of 18 requests while full snapshots restored 0 and full replay restored 9

## Wide graph topology study

Run `make topology-scaling` to reproduce the wide and deep graph planner comparison
The published output is in [milestone2/topology_scaling_oct11](milestone2/topology_scaling_oct11)
It contains 15 executable histories and 315 planner executions and 45 exact restores
The largest graph has 1038 nodes and 1068 edges and every solver run reached a proven optimum
All planner objectives agree and version 4 gave a 10.47 times median speedup over version 2 with a 98.21 percent median variable reduction

## New runs

The runner creates fresh output under results/runs and refuses an existing output folder
Those local runs are excluded from Git until selected evidence is reviewed for publication
Full generated capture archives and working policy stores are excluded from the compact package
The complete small replay example is kept in examples/captured_history and fresh histories can be regenerated

Moving the experiment folders changes their paths and does not change their timestamps or measured values
