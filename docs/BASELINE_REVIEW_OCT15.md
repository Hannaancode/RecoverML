# Baseline review on 15 October 2026

This is a critical review of the archived October 14 comparison and the baseline implementations inspected at the start of the October 15 audit. It does not change old results or the manuscript. New October 15 direct-baseline experiments should be assessed separately and can resolve the gaps listed here.

The existing evidence supports a narrow result: under the declared preprocessing replay losses and the shared physical-byte budget the tested RecoverML stores recover more protected requests than the tested materialization components. It does not establish general superiority over native HELIX or HYPPO and it does not establish superiority over all robustness-aware methods.

## Recorded checks

The executable audit is [audit_published_fairness.py](../scripts/audit_published_fairness.py) and its full results are [published_fairness.json](../results/validation/2026-10-15/scientific_audit/published_fairness.json).

The audit returned **PASS for the recorded invariants**:

- It checked all 560 summary rows and all 33,440 request traces across 56 bound cases
- Every one of the ten policies has exactly 3,344 recorded requests
- Every policy within a case has the same failure-scenario set and the same captured graph and environment
- Summary request and exact-recovery and blocked counts agree with the raw traces
- No main-policy store exceeds its permitted robust budget
- No trace records execution of a producer whose capability group was disabled
- All 560 archived policy stores have the selected payload identities and payload sizes stated by their planner records
- Total archived file sizes agree with reported retained bytes and the common manifest and capability-contract accounting
- Structural coverage computed from each archived store agrees with its recorded recovery outcomes
- The downloaded original HYPPO source matches the pinned SHA256

Archive hard links are resolved before counting sizes. An artifact linked to another archived policy still has its full logical file size in that policy's store. These checks use archive file-size metadata and the current structural certificate implementation and do not constitute a fresh execution of all historical models.

To run the audit from the repository root after installing the paper dependencies:

```bash
python scripts/audit_published_fairness.py \
  --hyppo-cache .cache/hyppo \
  --output results/runs/published_fairness_new.json
```

The original source is downloaded into the supplied cache if absent and its hash is checked before execution. Choose a new output filename because the command refuses to overwrite existing evidence.

## Tasks 2 to 5

| Task | Status for the inspected October 14 package | Evidence and remaining condition |
| --- | --- | --- |
| 2 Published-method baseline audit | PARTIAL | The tested HELIX rule matches its cited threshold and event semantics and the HYPPO source matches its pin and the adapters are disclosed but neither is a complete native-system reproduction |
| 3 Equal experimental conditions | PARTIAL | Recorded graphs and scenarios and shared execution and actual-byte accounting pass the checks above but the final published suite uses the RecoverML optimum as its main common budget and does not provide a common multi-budget coverage curve |
| 4 Stronger direct baselines | PARTIAL | A separate exact scenario formulation already exists and is compared on the saved tractable suites but a robustness-aware greedy method and stronger local improvement are absent from the inspected original suite |
| 5 Baseline sensitivity | PARTIAL | Read speeds and event tie order and loss bounds and some model and history sizes are covered but a frozen common-budget and nonuniform-cost and frequency and materialization-eligibility sensitivity study is not present in the original suite |

These are scope-level judgments and therefore the PASS on arithmetic and byte-accounting checks does not turn the entire task into PASS.

## What the baselines actually do

### HELIX

The primary paper is [HELIX in PVLDB 12(4)](https://www.vldb.org/pvldb/vol12/p446-xin.pdf). Algorithm 2 and Definitions 5 and 6 on printed pages 452 and 453 determine when a node is out of scope and compare its cumulative cost with twice its load cost.

In [helix_materializer.py](../src/recoverml/helix_materializer.py) the capture order is topological and a node becomes eligible after its last immediate child has completed and a unique logical ancestor set supplies its cumulative captured cost. Loading uses serialized bytes divided by the declared read speed and the inclusive remaining budget is checked before retention. Shared physical payloads are paid once.

This is a reasonable cold-capture decision-rule adapter. Native HELIX also has iterative reuse planning and computed versus loaded versus pruned node states and earlier-materialization eviction behavior. The adapter does not reproduce that complete execution lifecycle. Results should keep their existing decision-rule label and should not be renamed native HELIX runtime results.

The saved final comparison runs every combination of 50 and 200 and 800 MiB per second and capture and reverse order within an out-of-scope event. All six settings remain in the evidence. The best tested common-budget setting reaches 1,940 of 3,344 requests. This is a descriptive best-of-tested-settings value rather than a claim about the best possible HELIX configuration.

### HYPPO

The primary paper is [HYPPO at ICDE 2024](https://dsachar.net/publication/2024-icde-kss/) and the tested released code is [history_manager.py at the pinned revision](https://github.com/akontaxakis/HYPPO/blob/405e42de863272fcb71a625cf6b2ae0696c7a8c5/Components/history_manager.py).

[published_materializers.py](../src/recoverml/published_materializers.py) executes the original rank and frequency-weighted ranking functions unchanged. Their strict integer capacity comparison is converted to the shared inclusive capacity by passing budget plus one and the resulting selected bytes are checked against the original budget. This correction is mathematically valid for integer artifact sizes and does not grant extra usable storage.

There are material differences between the full published method and this component experiment:

- The paper's Section III materialization formulation on PDF pages 5 and 6 includes plan locality and a minimum-plan recomputation estimate whereas the released ranking functions use the supplied cost divided by artifact size with optional frequency weighting
- The project supplies captured logical-ancestry cost annotations rather than the complete native minimum-hyperpath cost estimator
- The project supplies per-version physical dependency counts rather than directly measured native HYPPO access counts
- The project represents every optional physical artifact as eligible and roots as raw so membership checkpoints are eligible even though the original functions normally exclude nodes explicitly typed as split
- The adapter supplies node attributes for the tested ranking functions and does not reconstruct the full native history and augmentation and execution system

The existing manuscript discloses these main scope boundaries. Keeping the released component is useful because it gives an exact reproducible software baseline. A full native-system reconstruction is not needed to establish whether the separate robust contract is implemented correctly. Strong direct baselines for the robust objective are the higher-priority missing comparison.

### Maximum versus minimum ancestry sensitivity

The original adapter assigns a physical artifact the maximum captured logical-ancestry cost across its producers. A concern is that this might overvalue an artifact with an expensive alternative producer compared with a cheaper route.

The new audit changed only that annotation to the minimum captured logical-ancestry cost across producers and reran the original HYPPO ranking functions on all 56 archived cases at the same budgets. **No selected set changed and no coverage count changed**. Rank remained at 2,240 and frequency remained at 2,291 of 3,344 requests.

This retrospective structural sensitivity weakens that specific explanation of the observed score gap. It does not prove that arbitrary graph adapters are harmless and it does not supply the complete native hyperpath estimator. The report preserves all 112 case and policy sensitivity records.

## The independent exact comparator already exists

[scenario_retention.py](../src/recoverml/scenario_retention.py) shares global physical retention variables across explicitly enumerated permitted loss sets and gives each loss set separate availability and replay choices. Continuous rank constraints reject self-supporting physical cycles. Roots are forced to be retained and every target must be available. The objective is physical payload bytes and the same fixed metadata is added to both compared stores.

It is a separately coded optimization formulation of the same contract. It is not an independently developed external system and it shares the project's validation and structural-certificate helpers. Those qualifications matter when using the word independent.

[test_scenario_retention.py](../tests/test_scenario_retention.py) compares both formulations against separately written exhaustive reachability on 20 small generated graphs and checks that a scenario-limit skip cannot be called certified. The saved [tabular suite](../results/research/paper_oct14/tabular/report.json) contains 48 matching planning cases and the [estimator suite](../results/research/paper_oct14/estimators/report.json) adds eight and the [broader-fault suite](../results/research/paper_oct14/fault_scope/report.json) records another 36 matching bound and scope cases. These cases must not be presented as independent samples of production workflows.

Adding another identical scenario MILP would duplicate completed work. More varied exhaustive cases and honest scale limits are useful extensions.

## Remaining fairness improvements that make sense

1. Add direct robust reverse-deletion and local-improvement retention methods using the same permitted loss scenarios and the same physical identities and the same target contract. Report actual retained bytes and certification cost and planning time. A heuristic that cannot fit a budget has not proved the budget infeasible.
2. Freeze a grid of common optional-byte budgets before running new cases. Include budgets below and at and above the exact robust optimum and report actual use as well as the limit. Below-optimum partial coverage is a different objective from guaranteed full recovery and should be labeled accordingly.
3. Preserve full snapshots and all-groups-off retention at their own storage points. A larger-budget result can show a useful tradeoff but cannot be admitted to a smaller common-budget comparison.
4. Sweep nonuniform stage-cost estimates and declared recovery frequencies and materialization eligibility and stable tie orders. Uniformly multiplying every HYPPO cost cannot change a cost-ratio ranking and would be a weak sensitivity test.
5. Keep timing claims separate. The published recovery timer starts after graph reading and restorer construction so it is not a complete cold end-to-end latency measurement. HYPPO and HELIX planning costs are not measured by the existing published comparison. The new experiment should time the selection functions themselves and rotate method order where timings are compared.
6. Retain settings where a heuristic matches the exact optimum or is faster and settings where snapshots have the better recovery latency. Those outcomes establish when the exact solver's additional planning work is worthwhile.

No GPU is needed for these checks and retention heuristics and CPU optimization. Larger neural workload evaluation is a separate resource decision and is not required to resolve the baseline fairness issues above.
