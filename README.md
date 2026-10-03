# RecoverML — Milestone 2 prototype

Recoverability-preserving artifact retention for versioned scikit-learn pipelines.

**Status:** working research prototype with measured preliminary results. This does not yet prove research novelty or practical superiority over strong simple baselines.

**Latest results:** 1,175/1,175 admitted version-2 restorations matched artifact hashes. Against v1 on matched feasible histories, median paired planning speedup is 19.3× and planning plus five restores improves 3.4×. Direct target snapshots remain competitive where they fit. Read the [second-iteration report](docs/ITERATION2_REPORT.md) and [planner formulation](docs/PLANNER_V2.md).

## Measured results

The second iteration contains **11,200 requests**, **80 captured histories**, four byte budgets, seven policies and five historical versions per history. All admitted requests from both proposed planners restored exactly. The complete request matrix and restoration traces passed the audit; all **22 correctness tests** passed.

| Policy | Complete history-budget selections | Exact version requests |
|---|---:|---:|
| Full deduplicated snapshots | 80 / 320 | 400 / 1,600 |
| Full replay | 100 / 320 | 500 / 1,600 |
| Cost-ranked cache | 210 / 320 | 1,099 / 1,600 |
| Pinned boundaries + cost cache | 200 / 320 | 1,000 / 1,600 |
| Direct target snapshots | 175 / 320 | 875 / 1,600 |
| Planner v1 | 235 / 320 | 1,175 / 1,600 |
| Planner v2 | **235 / 320** | **1,175 / 1,600** |

A complete selection restores every protected version within the same byte budget. Requests blocked by budget limits remain in the denominators. Successful latency comparisons require both policies to complete the same history and budget.

### Recovery under storage budgets

![Exact restoration success at each byte budget, including blocked requests](results/iteration2/success_by_budget.png)

### Planning cost and matched total cost

![Planning time by workload and paired speedup for planning plus five restorations](results/iteration2/paired_costs.png)

Case labels map to the workload table in the [report](docs/ITERATION2_REPORT.md#experimental-design). The right panel favors v2 above 1; direct target snapshots remain competitive. Costs exclude store materialization and initial environment validation.

### Storage and restoration latency

![Storage and warm-cache restoration latency for the controlled opaque-feature workload](results/iteration2/opaque_workload.png)

This plot compares full snapshots at the 100% budget with the other policies at 25%, as labeled. The approximately 91% storage saving is shared by direct target snapshots and v2.

[Planning-overhead plot](results/iteration2/planning_overhead.png) · [Raw requests](results/iteration2/raw_requests.csv) · [Execution traces](results/iteration2/execution_traces.jsonl) · [Retention plans](results/iteration2/retention_plans.jsonl) · [Paired comparisons](results/iteration2/paired_comparison.csv) · [Audit](results/iteration2/audit.json)

## What it does

1. Captures a dependency DAG, operator parameters, execution environment and SHA-256 artifact identities.
2. Deduplicates identical input blocks and intermediate artifacts across versions.
3. Protects each historical version's trained model and test-set probability predictions for every model branch. Two experimental cases additionally protect the normalized feature matrix.
4. Selects retained blobs under a byte budget. Version 2 uses a proved direct-target lower bound when applicable, otherwise a bounded global MILP with checked feasible incumbents. The original multi-start greedy policy remains a baseline and fallback.
5. Restores from the selected disk store, with no access to the capture archive, and checks each loaded or recomputed artifact hash.
6. Rejects unavailable replay paths, environment mismatches and corrupt artifacts.

Dependency scope and replay eligibility are separate properties. A fitted scaler depends on the training subset globally. Scaling is row-local only given the fitted parameters. Data mutations invalidate fitted state and downstream normalized data. A supported stochastic split or forest is replayable with recorded integer random seeds; an unavailable external enrichment response is not.

## Quick start

Use Python 3.12. The recorded run used Python 3.12.14 and the exact dependencies in `requirements.txt`. A fresh run captures the environment of its own machine. Cross-host bitwise replay is not promised.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
recoverml benchmark --config configs/smoke.json --out results/my_smoke
python -m recoverml.audit results/my_smoke
```

For the full repeated experiment and plots, run `make iteration2`. For the original experiment, use `configs/preliminary.json`. Both configurations and their measured results are included.

If you already have the dependencies, installation is optional: prefix commands with `PYTHONPATH=src` and use `python -m recoverml` instead of `recoverml`.

Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` before invocation. The harness also applies `threadpool_limits(1)`. Native Windows users can invoke these commands from a suitable Python environment; `source` is a Bash command.

Output directories must not already exist. `--resume` continues an interrupted run only when already checkpointed histories are complete and the configuration/environment match; partial-history resume is deliberately rejected.

## Replay a captured history

The distribution contains a complete small example in `examples/captured_history`. This is a captured experimental proxy for an external-feature pipeline. The external response bytes are present, but the generator state is intentionally unavailable.

```bash
recoverml select examples/captured_history --budget-bytes 2000000 --out work/retained
recoverml restore work/retained --version 0 --out work/restored_v0
```

On another execution environment, the supplied example may refuse restoration. Capture your own history with the benchmark command and then select from `results/my_smoke/capture_archives/case00-rep0`. Do not bypass the environment guard to claim exact replay.

`select` uses metadata for planning, then copies only the selected artifacts. `restore` reads only that selected store. The target files contain the prototype's artifact codec; `recoverml.core.unpack` reads them. Do not use ordinary `pickle.load` to load a canonical model artifact.

## Automated experiments

The original preliminary matrix has 11 cases × 5 independently captured histories × 4 budgets × 6 policies × 5 historical version requests = **6,600 request records**. The second iteration keeps those controls and adds five cases with four model branches sharing preprocessing: **16 cases × 5 repeats × 4 budgets × 7 policies × 5 versions = 11,200 requests**. The branching forest cases use 48 trees and starting depth 8; the original forest controls use 12 trees and starting depth 5. All policies in a history receive identical artifacts, targets and budgets. Both logistic regression and random forests are included. Synthetic workloads have 2,000 or 10,000 rows. The public Wisconsin diagnostic breast-cancer dataset has 569 rows; it is not enlarged or presented as a large dataset.

Changes are model-parameter edits or contiguous 1% record mutations. The contiguous mutation pattern creates explicit unchanged-block reuse opportunities; random scattered changes could reduce reuse. Every case records accuracy for context, but model accuracy is never used as the restoration correctness criterion.

Policies:

- `full_snapshot`: all artifacts with content deduplication; stronger storage baseline than separate duplicate snapshots.
- `full_replay`: required original input blocks and labels, then full replay.
- `cost_cache`: required inputs plus operation-cost-per-byte ranked artifacts; no coverage constraint.
- `pinned_cost`: additionally pins every unsupported-replay boundary, then cost-based caching.
- `target_snapshots`: required inputs plus all requested targets directly; intentionally strong simple baseline.
- `recoverability`: coverage-constrained multi-start reverse deletion and marginal-benefit additions.
- `recoverability_v2`: guarded direct-target shortcut, otherwise global load/replay/retention optimization with a 0.5-second solver limit. Solver status, optimality gap, validation and any fallback are logged. This is the default for the `select` CLI.

See `docs/PLANNER_V2.md` for the formulation and the shortcut's cost-model proof. MILP optimization is established prior work; using it does not itself establish research novelty.

The read-cost model uses 500 MB/s and 20 microseconds per blob plus measured capture operation times. This is a planning assumption, not a fitted storage benchmark. Actual restoration times are independently measured. Output artifact verification is included in restore latency; environment initialization, planning and store materialization are separate.

Budget counts **physical serialized blob bytes plus manifest bytes**, including input history and fitted state. It excludes filesystem allocation overhead, diagnostic certificates, benchmark logs, and the full capture/oracle archive. The planner is offline: its initial enumeration of captured candidates is not claimed to obey an online peak-storage budget.

Every failed or blocked request remains in `raw_requests.csv`. Successful-latency summaries explicitly condition on success. A policy's selection failure is not a zero-millisecond restore. A heuristic inability to fit is not a mathematical infeasibility proof.

## Results and artifacts

Read the [latest report](docs/ITERATION2_REPORT.md) and the [preserved original report](docs/PRELIMINARY_REPORT.md) before interpreting the plots. Included results:

- `results/preliminary/raw_requests.csv`: every request, including failures and budgets.
- `results/preliminary/execution_traces.jsonl`: capture and restoration operation events.
- `results/preliminary/retention_plans.jsonl`: retained sets, decision traces and structural reconstruction certificates.
- `results/preliminary/capture_metrics.csv`: execution and lineage/serialization timings.
- `results/preliminary/oracle_comparison.csv`: 72 small-instance exact comparisons.
- `results/preliminary/oracle_fixtures.json`: complete graph fixtures for the exact reference.
- `results/preliminary/audit.json` and `trace_repairs.json`: export audit and explicitly recorded re-executions.
- `results/preliminary/environment.json`, `config.json`, `histories.json`: experiment provenance.
- Three preliminary PNG plots and machine-readable summaries.
- `results/test_results.txt`: correctness test output (22 passing tests).
- `results/iteration2/`: the new raw requests, full operation traces, selection diagnostics, capture metrics, exact-reference comparisons, experiment provenance, audit and plots.
- `results/iteration2/paired_comparison.csv`: matched histories where both policies restore every version, with planning charged once plus five measured restores.
- `results/iteration2/comparison_findings.json`: coverage counts, paired cost ratios and solver-path diagnostics.

`make iteration2` runs the new matrix, audit, standard plots, paired comparisons and both planners' tiny exact-reference comparisons. Alternatively, use `python -m recoverml benchmark --config configs/iteration2.json --out results/my_iteration2`, then the commands in the Makefile with that directory. Output directories must be new. The development pilot is not part of the reported five-repeat results.

Run `python -m recoverml.audit results/my_preliminary` to verify request/operation trace consistency. An explicit `--repair` re-executes incomplete selections from the original capture archive and preserves original request measurements.

Full captured payloads for all benchmark histories are intentionally excluded from the compact distribution. The complete example is included. All original request/operation traces are included. Fresh reruns of the opaque-feature cases generate new external-response realizations; they do not reproduce the original hashes unless the original response artifacts are retained.

## Scope and limitations

- Offline finite-history planner; no crash-safe online admission/eviction manager, distributed runtime, GUI or arbitrary Python instrumentation.
- Explicit supported operators only. No automatic determination of whether arbitrary functions are deterministic.
- Certificates establish structural recoverability under declared contracts; hashes are checked at execution. Hashes do not recreate missing information or prove dependency completeness.
- Version 1 is a heuristic. Version 2 establishes estimated optimality only when its shortcut applies or the solver proves optimality; a bounded incumbent or fallback has no such guarantee. Actual runtime optimality is not promised. Exact enumeration is restricted to small graphs.
- The canonical model codec normalizes unused C-struct padding and encodes supported learned state, so exactness concerns **defined serialized artifact identity**, not raw process memory or arbitrary stock-pickle output.
- Pickled array/state artifacts are trusted local research files. Do not load untrusted pickle stores.
- Fresh Python memoization per request, but OS page cache is not flushed. Sub-millisecond loading times are warm-cache measurements, not cold-disk performance.
- Planning overhead is amortized only if a selected retention plan is used for repeated restorations. No claim that end-to-end latency always improves.
- No LIMA/Helix/Kishu implementation was executed. The named baseline policies are our implementations, not performance results for those published systems.

## Research references

- LIMA, SIGMOD 2021: https://mboehm7.github.io/resources/sigmod2021a_lima.pdf
- Helix, PVLDB 2019: https://www.vldb.org/pvldb/vol12/p446-xin.pdf
- Kishu, PVLDB 18(4): https://www.vldb.org/pvldb/vol18/p970-li.pdf
- ElasticNotebook: https://arxiv.org/abs/2309.11083
- ExoFlow, OSDI 2023: https://www.usenix.org/system/files/osdi23-zhuang.pdf
- Wisconsin dataset API and original-source references: https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_breast_cancer.html
- Randomness semantics: https://scikit-learn.org/stable/common_pitfalls.html#controlling-randomness

## Milestone submission status

The working prototype, automated benchmark harness, raw CSV/JSONL logs, performance plots and reports are included. The [submission guide](docs/SUBMISSION.md) describes instructor review and reproduction. The experimental reports preserve the publication status at the time each local experiment was recorded.
