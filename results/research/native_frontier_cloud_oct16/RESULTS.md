# Paired native frontier recovery: final revision 4

Completed 16 October 2026. Runtime source: `f00981ea84357199f0bde6916a5536684b1ed567`.
[GitHub run 38953068522](https://github.com/Hannaancode/RecoverML/actions/runs/38953068522) completed all three fixed seed blocks.
The separately coded evidence checker passes for all original artifact members, captured payload hashes, cache budgets, retained sets, commands and target identities.
This is an internal reproducibility check, not an external peer review.

## Final result

| Recovery stratum | Histories | RecoverML faster | Median paired DVC/RecoverML elapsed-time ratio |
|---|---:|---:|---:|
| Downstream computation required | 18 | 18 | 2.1856 |
| Every target file already retained | 18 | 18 | 9.9067 |
| Complete grid | 36 | 36 | Report the two strata above |

Both methods use the **same optimal retained payloads and the same common payload-byte budget**.
There is no storage win over this manually optimized DVC frontier.
There are 216 successful full-history subprocess commands and 12,096 exact target-file hash checks.
Each history has three paired, randomized-order trials per method.
Reported speedups are medians of per-history ratios of median elapsed times; requests and repetitions are not independent workloads.
All cases are retained. See [complete audit](v4/complete_audit.json) and [full-grid figure](final_comparison.png).

The grid is two public datasets (Wine, Breast Cancer), three seeds (20261016/17/18),
three history sizes (4/16/64 versions), and two capture boundaries (fused/combined).
These are constructed histories on GitHub runners, not a production trace or a population estimate.

## What was timed and paid for

Both commands must materialize every requested historical model/prediction file and verify its captured SHA-256.
Native DVC receives the certified retained set without paying for optimization and uses one batched downstream stage.
A correctly populated DVC cache can skip that stage when all targets are already retained.
Before each trial, only paid retained payload objects remain in the cache; hard links avoid charging a second physical copy.
The checker reconciles distinct-inode cache bytes with the paid payload budget and all output identities.
DVC-specific configuration is recorded separately from common payload accounting.

Elapsed time includes subprocess/CLI bootstrap and final byte verification; setup/retention planning is excluded.
Core worker timings, command output and CPU receipts are retained separately.
OS caches are not flushed. No warm-service, network, remote checkout or general DVC performance claim follows.
Retired view entry points are guarded in this experiment, rather than physically uninstalled.
The earlier retinal control separately demonstrates physical legacy-module removal.

Revision 4 adds `recoverml.file_export`: a standard-library path for hash-checked export of fully retained target files.
It avoids model deserialization and numerical-library startup when replay is unnecessary, and falls back to the ordinary restorer when targets are absent.
The same helper is available to both authored workers. Exact file export makes no claim that the serialized model can execute in an incompatible environment.
Existing model-loading environment checks remain in force.

## Baseline corrections and negative results retained

| Version | Runtime source | Actions run | Interpretation |
|---|---|---|---|
| Initial setup attempt | b8ae201 | 38947760758 | Setup unpacking error before timing; not a DVC failure |
| v1 | 41861a9 | 38948170791 | Completed; superseded because its DVC worker unnecessarily deserialized newly computed payloads |
| v2 | e0c745a | 38949922822 | Completed; superseded because cache clearing forced unnecessary retained-target work |
| v3 | dd17998 | 38951808344 | Correct paid cache; RecoverML faster in 18 recomputation cases, DVC faster in all 18 retained-target cases |
| v4 | f00981e | 38953068522 | Same proper cache plus general exact-file export; final full grid above |

In v3, the median DVC/RecoverML ratio was 2.3256 for recomputation and 0.5589 for retained targets.
That mixed outcome motivated the product change. Versions are distinct exploratory development stages, not additional trials pooled with v4.
The final protocol is recorded before its own run, after earlier exploratory findings; this is not an independently preregistered confirmatory study.
All superseded compact evidence is preserved byte-for-byte in `baseline_parts`, with transport and per-file identities in `baseline_archives.json`.
The setup-failure original ZIPs are under `results/validation/2026-10-16/native_attempt_1`.
No negative execution record was replaced with a successful rerun.

## Recheck from a clone

Use the pinned Linux/Python 3.12 environment from `reproducibility.txt` and retain Git history for source checks:

```sh
PYTHONPATH=src python scripts/audit_native_frontier.py results/research/native_frontier_cloud_oct16/v4 --source-commit f00981ea84357199f0bde6916a5536684b1ed567 --output work/fresh_native_audit.json
python scripts/materialize_native_baselines.py --output work/native_baselines
```

The materializer verifies every part, assembled transport archive and extracted member, and refuses existing output.
Expanded v1/v2/v3 files preserve their original inner capture/receipt archives and original GitHub ZIP-member inventories.
Artifact receipts explain which individual members are represented by those byte-identical original inner archives.
Old auditor snapshots in validation record historical checker identity; use the current checker with each version's runtime source to inspect older grids.
Model payloads need not be loaded to audit the preserved records.

The release verifier also checks committed file bytes and ledgers. Its available-file checks can pass while
`release_complete=false`: one original historical Letter archive container is still missing.
Its separately verified payload reconstruction does not repair that original-container identity.
Human course reviews remain unassigned, and the October 14 manuscript/PDF has not been revised.
