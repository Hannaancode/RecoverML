# Saved evidence and statistics review

This review examines the evidence that is present in the repository and the ignored local working folders on 15 October 2026
It does not change the manuscript or earlier measurements and it cannot reconstruct experiments that were never recorded

The executable inventory is [scientific_inventory.py](../scripts/scientific_inventory.py) and its full output is [inventory.json](../results/validation/2026-10-15/scientific_audit/inventory.json) with a readable [directory inventory](../results/validation/2026-10-15/scientific_audit/inventory.md)

```bash
python scripts/scientific_inventory.py \
  --output results/validation/2026-10-15/scientific_audit \
  --regenerate-figures
```

The command updates only its new audit output and temporary figure copies and leaves the earlier evidence untouched
The inventory records local directories that will not exist in a clean clone and distinguishes those from the tracked evidence

## Task status

| Task | Status | What the evidence establishes and what remains |
|---|---|---|
| 1 All experiment inventory and selection | PARTIAL | Current saved and local directories and generator hashes and available source snapshots are inventoried but no prospective registry existed and the cause of every incomplete local run cannot be recovered |
| 19 Correct statistical analysis | PARTIAL | Current paper counts and descriptive medians do not treat repeated requests as independent samples and this audit names the matched blocks and aggregation rules but one older frontier summary has an independence defect and three seeds cannot establish population reliability |
| 20 Negative and conditional results | PARTIAL | Known zero savings and baseline failures and slow planner cases and serialization diagnostics and the strict-capacity pilot are preserved but unrecorded selection history cannot be certified complete |
| 21 Headline numbers and figures | PARTIAL | The current primary raw rows and all nine paper figures and generated result tables reproduce and the named headline denominators agree but this does not mean that every historical prose claim has been independently re-executed |
| 22 Reproduction package | PARTIAL | Pinned direct dependencies and the guide and source hashes and raw stores and same-host clean-install evidence exist and the October14 GitHub workflows passed but CI for the later audit changes and full paper reproduction on another machine remain separate checks |

## Verified current counts

| Evidence folder under results/research/paper_oct14 | Captures | Planning cases | Requests across all policies | Exact RecoverML requests |
|---|---:|---:|---:|---:|
| tabular | 24 | 48 | 28512 | 3168 / 3168 |
| estimators | 4 | 8 | 1584 | 176 / 176 |
| published | 28 | 56 | 33440 | 3344 / 3344 |

Every summary row in these three matrices agrees with the corresponding raw case and policy counts and every request identity is unique within the declared case and policy and version and disabled-group tuple
All these saved disk traces record that the captured in-memory payload archive was absent and all recorded start and end timestamps are ordered
These consistency checks audit saved execution evidence and do not claim to be new executions on another machine

The published comparison has 2240 exact HYPPO rank requests and 2291 exact HYPPO frequency requests and the best tested common-budget HELIX setting has 1940 exact requests out of the same 3344 denominator
The HELIX snapshot-budget row uses a larger byte budget and is separate
These comparisons execute released HYPPO components and a HELIX decision-rule reimplementation through a common executor and they do not execute complete native HELIX or HYPPO systems

The merged graph has 112 protected versions from 12 captured branches and 2464 exact requests and remains one merged graph
The component experiment has 118 planner rows and 9288 exact disk requests and the broader fault experiment has 36 scope cases and 3920 exact requests

## What the storage headline means

The 20.26355556 percent headline is the unweighted mean of 48 case-level saving percentages
The median case saves 13.95840017 percent and the range is zero to 44.33742097 percent and nine cases have zero saving
The ratio of total retained bytes to total snapshot bytes over the same cases gives 15.17422476 percent saving and answers a different aggregation question

| Tabular subset | Cases | Mean saving |
|---|---:|---:|
| Lossless NPY and one loss | 12 | 36.10420910% |
| Lossless NPY and two losses | 12 | 14.98391333% |
| Rounded CSV and one loss | 12 | 14.98304991% |
| Rounded CSV and two losses | 12 | 14.98304991% |

The two bounds reuse each captured history and the two import formats reuse each dataset and split seed
The 48 tabular planning cases therefore are not 48 independent sampled workflows and the 24 captures contain 12 matched dataset and seed blocks on four fixed public datasets
Likewise the two Digits model types reuse their underlying dataset and split seeds
Request totals measure exhaustive coverage of the declared small fault universe rather than a statistical sample size and do not show the frequency of these failures in deployed ML systems

The 112-version saving is a result for the stated feature-replay loss contract and the actual captured alternatives
When both model fitting and prediction may fail the broader controls require full target snapshots and their saving is zero
This is a material limit on practical storage benefits and is retained in the evidence

## Planner and timing qualifications

The original global counterexample solver is slower than the expanded exact solver in the six-group one-loss and two-loss cases and the twelve-group one-loss case
It is also slower on the original mixed two-loss graph and the separate component timings are later descriptive phases on the same host
The 434.89 times index result concerns only certificate construction on a generated depth-2048 chain and does not measure complete model restoration

The older frontier study in results/milestone2/frontier_scaling_oct10 reuses three seeds across five depths
Its summary calls the 15 depth and seed combinations independent and its original bootstrap and Wilcoxon calculation use those combinations separately
The old measurements and statistics remain available and this audit adds a separate whole-seed resampling calculation in inventory.json
With only three seed blocks this remains exploratory and the original unclustered p-value should not be presented as strong independent evidence
The later boundary-control manuscript table already uses a separate whole-seed calculation through src/recoverml/paper_evidence.py and that correction should not be confused with the earlier frontier result

## What is preserved and what is still unknown

The strict-capacity pilot is in results/research/paper_oct14/protocol_pilot and its stdout is preserved in diagnostics/paper_tabular_oct14.log
The initial neural serialization failure is in diagnostics/paper_estimators_oct14.log and the corrected canonical inference study has its own estimators folder and source copies
The earlier nonfinite text-model diagnostics and native checkpoints remain in results/archive and are excluded from final finite-output quality claims

The local directory results/runs/frontier_scaling_oct10_failed_run1 contains a config and captured manifests but no terminal error log or completion report
Its name is evidence of an incomplete diagnostic and does not establish its failure cause
The incomplete local results/runs/paper_estimators_oct14 has stored files but no complete report and its serialization exception is documented separately
The inventory also records earlier witness pilots and working copies and it identifies byte-identical published copies where enough shared evidence exists
The existence of these directories cannot establish that the experiment-selection process was fully prospective or that every unrecorded attempt is known

All report generator and dependency identities that the inventory can match are linked to their current or preserved source files
Older provenance may have fewer recorded dependencies and complete dependency capture is not inferred from a single generator hash
The inventory separately lists any recorded source identity it cannot match
Fourteen older references initially lacked a matching current or copied source file and all fourteen were then resolved to eight genuine historical Git blobs
The eight exact source versions are now copied into [recovered_source_versions](../results/validation/2026-10-15/scientific_audit/recovered_source_versions) and recovery_index.json records their original module and Git object and verified SHA256
This adds readable source provenance without changing any earlier execution logs or source identities

## Figure and reproduction checks

Both current analysis programs regenerated all nine PNG figures byte for byte and both generated measured-results Markdown tables byte for byte
Their JSON claim ledgers are semantically identical and differences in object key ordering do not change their content
The inventory records the original and regenerated hashes when run with --regenerate-figures

Before the new implementation work began both existing checksum manifests matched every listed file
While the parallel review makes real source changes the old manifests naturally become stale and the final manifests must be refreshed after all new work is saved
The inventory records the state observed at its execution time and its own generation does not certify a later working tree

The recorded isolated installation on 14 October used the same host and passed 72 tests with five optional PyTorch skips and regenerated nine figures
The earlier optional CPU PyTorch validation is a separate 49-test run
Neither should be described as proof that all 77 tests ran with PyTorch present
The new parallel audit has separately installed CPU PyTorch and run the expanded 100-test suite successfully and its [fresh validation log](../results/validation/2026-10-15/scientific_audit/tests_with_torch.txt) belongs to that new checkpoint rather than replacing either earlier result
The [GitHub Actions receipt](../results/validation/2026-10-15/scientific_audit/github_ci_oct14.json) records successful main and research branch workflow runs for the October14 commit 5b41e14fb88d070a194a116dd258985787e49cb4
The workflow includes the smoke benchmark and CPU PyTorch job and this is stronger evidence than merely configuring a job
It still does not execute the complete paper matrix on another machine and it does not validate later uncommitted audit changes

## Useful next evidence

The most useful additions are a prospective locked workload and budget matrix and a direct robustness-aware heuristic comparison and workflows with genuinely different operator structures
A new restoration-cost analysis should retain all failure denominators and compare successful-request latency separately from recovery coverage
The paper should remain clear that exact inference checkpoints do not contain optimizer state for resuming training and that a different machine must respect the recorded numerical environment checks
An independent review of the objective and its prior literature remains necessary for a strong novelty claim
These evidence gaps require no GPU by themselves
