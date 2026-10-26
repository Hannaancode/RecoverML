# Broad recovery census: fixed protocol, 26 October 2026

The earlier 36-history native comparison was an exploratory constructed grid.
It does not estimate the frequency of wins in production.
This follow-up fixes a larger finite catalogue before full execution and reports a census of it.

## Population, units and primary claim gate

The full catalogue has six public built-in datasets (Iris, Wine, Breast Cancer, Digits, Diabetes and Linnerud);
four classification/regression recipe families (standardized linear, PCA plus neighbors, min-max plus tree,
and robust-scaled forest); and history lengths 1, 4 and 16.
Each of these 72 captures is evaluated under three loss contracts (intact, preprocessing, broad fitting/prediction),
two request sizes (latest targets, all targets), and two interfaces (CLI and warm API).
That yields **864 workload configurations and 7,776 paired method trials**, not 864 independent datasets.
Latest/all requests coincide for a one-version history; they remain explicit catalogue cells.
The split seeds and hyperparameter sequences are deterministic and fixed in source. Linnerud uses its first regression response.

The machine-readable protocol is `configs/recovery_census_oct26.json`.
A substantial case win requires a median DVC/RecoverML elapsed-time ratio of at least 1.10 across three paired repetitions.
The primary gate requires these wins in at least **90% within every dataset, recipe, loss, request-size and interface stratum**,
and exact recovery in every trial. Failures and missing cases never become wins.
Every recipe, loss, request size and interface stratum must be reported, including unfavorable outcomes.
No configuration is added, removed or reweighted after seeing full-study timings.

The catalogue is authored, includes previously used datasets and is not a random production sample.
Passing this gate supports a statement about this finite benchmark only.
It cannot establish faster recovery in 90% of unknown deployments.
Repetitions, related histories, losses and interfaces are not independent samples for a population confidence claim.

## Fair native baseline and direct control

DVC receives the same certified optimal retained payloads without paying selection cost.
Both output directories start empty.
Only paid retained cache objects survive preparation, hard-linked to their stored payloads; inode accounting checks physical bytes.
DVC uses native checkout when all requested files are retained and one exact-request batch repro otherwise.
It is not required to rebuild unrelated historical targets.
The API path uses warm imports with per-request Repo construction included; all methods share the controlled child environment.
The CLI path includes startup. Final requested-file inventory and SHA-256 verification are inside the primary timing.
Log writing, setup, capture and cache preparation are outside it; OS caches are not flushed.

The pinned native APIs are documented by the official
[DVC 3.67.1 checkout source](https://github.com/iterative/dvc/blob/3.67.1/dvc/repo/checkout.py)
and [reproduce source](https://github.com/iterative/dvc/blob/3.67.1/dvc/repo/reproduce.py).
The baseline chooses its command from the structural availability condition before timing.

A third, separately coded direct executor runs on the same inputs and shares the retained-file export helper.
Its complete results distinguish DVC orchestration overhead from recovery-core performance.
A DVC win alone must not be presented as beating every recovery engine.
The DVC worker also uses this direct executor rather than RecoverML's witness planner.

Capability losses are declared guarded entry points; they do not delete implementation modules.
The older retinal experiment remains the separate physical-retirement evidence.
All model fits, prediction values and source identities are captured fresh under the pinned runtime.
Capture archives remain an oracle for verification and cannot supply omitted runtime files.

## Engineering change

Retained-file export accepts an explicit protected-target request.
A request for available historical targets can avoid loading numerical/model libraries even when unrelated targets are absent.
Mixed requests use the existing checked witness restorer and verify every exported file.
Retained-store discovery enumerates actual files rather than probing every captured candidate.
Unknown files cannot become recovery sources, and corrupt retained files still fail closed.
DVC and the direct control can use the same selective export path.

## Execution and evidence

A separate Linux acceptance job must recover every smoke request exactly before any full matrix job starts.
Its measurements are excluded from the census.
The full workflow has 24 dataset/recipe blocks and retains failures and raw repetitions.
Source snapshots, capture payload archives, native configuration, command/API logs, selected sets, per-trial output hashes
and independent audits are retained. Full evidence must be copied into the repository before a completed claim.

Initial Windows preflight attempts found read-only cache removal and API working-directory/child-environment integration bugs.
They are excluded setup/debugging evidence, not native DVC defeats.
The corrected integration must pass acceptance before the frozen full run.

Use fresh output paths in the pinned environment:

```sh
PYTHONPATH=src python scripts/benchmark_recovery_census.py --dataset iris --recipe standard_linear --output work/new_census_block
PYTHONPATH=src python scripts/audit_recovery_census.py work/new_census_block --output work/new_census_audit.json
```

The full timing matrix ran at source 5174f3a669df73fa963a0003c6db2af49a9538be in Actions run 40337905283.
The initial block audits failed because canonical JSON sorts version keys lexically while requests use numeric order.
The checker now reconstructs the frozen numeric order explicitly and a 16-version regression test covers this case.
The original timing artifacts and failed audit statuses are preserved. A separate verification-only workflow rechecks those
same artifacts; no workload, trial, threshold or measured time is changed.

The corrected [verification-only run 40340457810](https://github.com/Hannaancode/RecoverML/actions/runs/40340457810)
passes all 24 blocks. The [complete results and original artifacts](../results/research/recovery_census_oct26/RESULTS.md)
confirm 864/864 substantial DVC wins, with 1.6952x CLI and 48.3212x warm-API median paired speedups,
7,776/7,776 exact trials and 54,540 target hash checks. Every fixed stratum exceeds the 90% gate.
The direct executor remains near parity and has faster cases. No population probability or universal superiority follows.

To audit all preserved artifacts without repeating timings:

```sh
PYTHONPATH=src python scripts/audit_recovery_census_release.py results/research/recovery_census_oct26 --output work/new_complete_census_audit.json
```
