# Verified tables for the next draft

Evidence cutoff: research commit `e0c745a754599e45562067197da76ea7de0dd0e5`.
These are drafting inputs rather than a revised manuscript. All numbers below
come from the linked recorded studies. The [manifest](evidence_manifest.json)
binds their source bytes and the generated CSV tables to the cutoff.

## Main result: contract and capture boundary matter

The new cloud study has **36 constructed histories** on Wine and Breast Cancer
with three seeds and 4, 16 or 64 versions and two capture boundaries. The same
captures receive two failure contracts, giving **72 paired history/contract
cases**. These are not 72 independent histories. Shared loss places both
standardization views in one declared loss group. The optional materialized
concat changes the recorded recovery choices.

| Contract | Cases | Smaller than strong local search | Same bytes | Larger | Largest reduction | Median reduction across all cases | Manual frontier ties |
|---|---:|---:|---:|---:|---:|---:|---:|
| Separate entrypoints | 36 | 6 | 30 | 0 | 0.1942% | 0% | 36 |
| Shared preprocessing entrypoint | 36 | 9 | 27 | 0 | 48.7380% | 0% | 36 |

The six separate-contract differences are only 129 bytes each. They are
serialization differences rather than evidence of a substantial storage gain.
The largest shared-contract case is Wine / seed 20261016 / 64 versions / fused:
138,618 retained bytes versus 270,411 for local search, saving 131,793 bytes.
All 18 shared-contract concat controls tie local search. Both exact engines
agree on all 72 minima. The manual frontier matches every minimum; it is a
retention-set control and is not a new native DVC timing measurement.

Sources: [complete audit](../../results/research/strong_baseline_cloud_oct16/complete_audit.json),
[all 72 cases](cloud_storage_cases.csv),
[all 648 method rows](cloud_methods.csv),
[18 method summaries](cloud_method_summary.csv).

## Coverage of published-policy adapters at a common minimum budget

| Method | Separate: fully recoverable cases / 36 | Shared: fully recoverable cases / 36 |
|---|---:|---:|
| RecoverML exact | 36 | 36 |
| HYPPO rank adapter | 18 | 18 |
| HYPPO frequency adapter | 21 | 21 |
| HELIX rule adapter | 15 | 15 |

These are explicitly scoped adapters with a future-reuse objective rather than
the complete historical preservation objective. HYPPO uses a pinned released
component and HELIX is a rule implementation; this is not a full native-system
comparison. Both robust heuristics and target snapshots receive the full
candidate budget when comparing complete store sizes. Report budgets beside
coverage and do not describe these results as general system superiority.

## Actual cloud execution ledger

| Contract | Unique executed requests | Exact | Expected blocked | Unexpected |
|---|---:|---:|---:|---:|
| Separate | 12,180 | 9,963 | 2,217 | 0 |
| Shared | 7,472 | 6,147 | 1,325 | 0 |
| Total | 19,652 | 16,110 | 3,542 | 0 |

Identical retained stores share explicitly attributed executions. Do not sum
the method-level request counts to obtain unique runs. RecoverML's attributed
requests are 3,024/3,024 exact under separate loss and 2,016/2,016 under shared
loss. Expected blocked requests belong to infeasible comparator stores and
are different from unexpected execution errors.

## Planning time, separate from restoration time

| Study / subset | Cases | Faster than local | Slower than local | Median paired planning ratio vs local | Vs scenario exact |
|---|---:|---:|---:|---:|---:|
| New cloud / separate | 36 | See all case rows | See all case rows | 11.92x | 2.28x |
| New cloud / shared | 36 | See all case rows | See all case rows | 16.88x | 1.73x |
| Earlier scientific cases / all | 48 | 44 | 4 | 4.20x | 2.18x |
| Earlier cases / DAG eligible | 36 | 36 | 0 | 6.27x | 2.85x |
| Earlier cases / general fallback | 12 | 8 | 4 | 1.64x | 0.93x |

A ratio above one means RecoverML planned faster. These are medians of paired
ratios, not ratios of pooled means. The new cloud study has three planner calls
per method/case and the earlier timing study has five. They are descriptive
host measurements on correlated histories. The earlier study replans recorded
metadata; it does not repeat model recovery. Include all four slower local
comparisons and the fallback's slower median versus scenario exact.

Source: [48 complete timing rows](planner_timing_cases.csv) and the cloud audit.
The native DVC batch **v2** comparison is pending at this cutoff and must not
be inferred from these planning measurements or pooled with its earlier v1 run.

## Application and large-payload studies

| Evidence | Completed result | Scope to keep beside it |
|---|---|---|
| Scientific matrix | 36,480 requests: 15,420 exact and 21,060 expected blocked; zero unexpected | Eight constructed histories and a range of budgets; strong local ties all 48 full-budget storage cases |
| Retinal study | 10,920/10,920 exact requests; 12 storage wins and 96 ties versus simple greedy; 108 ties versus strong local | EyeAI-inspired public STARE workflow, not the private EyeAI clinical system; repeated conditions share 20 images |
| Native retinal DVC | All 32 target files exact; manually selected frontier matches 2,523,881 common bytes | Physical legacy-code retirement control; one descriptive timing run |
| Letter preprocessing loss | 3,669,545,821 snapshot bytes versus 4,829,269 retained bytes | 16 actually trained forests; strong robust heuristics match the saving |
| Letter broad loss | 3,669,548,445 bytes for both snapshots and exact store; zero saving | Structural storage result; not a fresh broad-loss runtime experiment |

Letter saves **3,664,716,552 bytes = 3.6647 decimal GB** in the uncompressed
canonical representation, or 99.8684%. With the measured gzip representation,
291,175,536 snapshot bytes become 568,375 retained bytes, saving
**290,607,161 bytes = 290.61 decimal MB**. The compressed one-GB goal is not met.
Native-pickle and native-gzip controls use different representations and belong
in a separate table rather than being mixed with canonical bytes.

There are 48/48 actual exact Letter recoveries across three unique stores. The
800 structural checks and their 799 feasible results are not 800 executions.
The large retained frontier averages about 6.65 seconds per version versus
2.12 seconds for snapshots in the descriptive run. Storage savings can require
more recomputation.

Sources: [scientific](../../results/research/scientific_complete_oct16/report.json),
[retinal](../../results/research/eyeai_complete_oct15/analysis.json),
[Letter](../../results/research/gigabyte_letter_oct16/analysis.json),
[native retinal control](../../results/research/eyeai_complete_oct15/native_dvc_repro/report.json).

## Verification and provenance notes

The fresh drafting audit passed all six seed/contract blocks and reproduced
the published aggregate report as the same JSON object. Its
[receipt](audit_receipt.json) preserves both file hashes, which differ because
of serialization. This was an evidence recheck rather than another measured
experiment. The recorded cloud full suite ran 131 tests with six skipped:
125 passed. This does not establish that the full runner works on Windows.

The scientific matrix's original six nonforest histories lack a closed global
end-of-run source guard after an interruption. Their snapshots, per-request
guards and reconciled original logs remain available. Retain this qualification.
One original Letter archive container remains missing; the recovered original
payloads have matching hashes and their replacement transport archive has a
different identity. Do not describe the original archive release as complete.
