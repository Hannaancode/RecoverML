# Research artifact guide

This guide maps the executable system, fixed protocols and saved evidence. Detailed installation and command sequences are in [reproducibility.txt](../reproducibility.txt).

## Entry points

| Purpose | Entry point |
|---|---|
| Overview and headline results | [README](../README.md) |
| Setup, saved-data checks and fresh runs | [Reproduction guide](../reproducibility.txt) |
| Capturing and restoring a small history | [Captured example](../examples/captured_history) |
| Correctness tests | `python -m unittest discover -s tests -v` |
| Automated storage and concurrency experiment | `bash run_benchmarks.sh` |
| Archived October 14 paper matrix | `bash scripts/run_paper_benchmarks.sh results/runs/paper_reproduction_01` |
| Committed-byte and raw-ledger checks | `python scripts/verify_release.py` |
| Retinal transport-part reconstruction | `python scripts/materialize_evidence.py` |
| Experiment inventory | [Results index](../results/README.md) |

Use a new output directory for each fresh run. Saved-data audits inspect existing records and are not new execution measurements.

## Main research studies

| Study | Protocol and results | Evidence |
|---|---|---|
| Coupled delta storage, 27 October | [Protocol and proof boundary](DELTA_STORAGE_OCT27.md) | Implementation and acceptance tests complete; the fixed 446-condition evaluation is pending. No new aggregate superiority claim yet. |
| Lossless storage, 26 October | [Fresh protocol](ENCODED_STORAGE_OCT26.md), [frozen transfer](ENCODED_TRANSFER_OCT26.md), [results](../results/research/encoded_storage_oct26/RESULTS.md) | 216 fresh conditions, 4,536 requests and all 230 older transfer conditions; 28 original artifacts, stronger gzip controls and explicit unavailable objectives |
| Broad recovery census, 26 October | [Protocol](RECOVERY_CENSUS_OCT26.md), [results](../results/research/recovery_census_oct26/RESULTS.md) | All 864 fixed configurations, 7,776 method trials and 54,540 target hash checks; 24 original execution artifacts and separate corrected audit artifact |
| Planner efficiency, 26 October | [Protocol](PLANNER_EFFICIENCY_OCT26.md), [results](../results/research/planner_efficiency_oct26/RESULTS.md) | All 230 frozen conditions plus 24 scaling controls; 2,904 paired timing calls, retained sets, original artifact ZIPs and audits |
| Three-seed separate/shared preprocessing loss | [Protocol](STRONG_BASELINE_FOLLOWUP_OCT16.md), [results](../results/research/strong_baseline_cloud_oct16/RESULTS.md) | Per-seed captures, raw ledgers, planning repetitions and integer flow certificates |
| Native DVC recovery at equal storage | [Protocol](NATIVE_FRONTIER_PROTOCOL_OCT16.md), [results](../results/research/native_frontier_cloud_oct16/RESULTS.md) | Final revision in `v4/`; earlier revisions are separately labelled |
| Scientific multi-budget matrix | [Protocol](SCIENTIFIC_PROTOCOL_OCT15.md), [results](../results/research/scientific_complete_oct16/RESULTS.md) | Eight captures, 1,920 method-budget rows and 36,480 actual requests |
| Retinal processing revision | [Protocol](EYEAI_PROTOCOL_OCT15.md), [reproduction](EYEAI_REPRODUCTION.md), [results](../results/research/eyeai_complete_oct15/RESULTS.md) | 18 public-image histories, 10,920 exact requests and native retirement control |
| Letter large-payload study | [Protocol](GIGABYTE_PROTOCOL_OCT15.md), [results](../results/research/gigabyte_letter_oct16/RESULTS.md) | Canonical/gzip accounting, raw replay receipts and payload identities |
| Earlier concurrency | [Performance report](reports/PERFORMANCE_REPORT.md) | 54 trials, 5,400 requests, CPU/RSS samples and throughput/latency figures |

## Design and validation

- [DAG specialization and proof scope](TRACTABLE_SUBCLASS_OCT15.md)
- [Correctness assessment](CORRECTNESS_REVIEW_OCT15.md)
- [Comparator definitions and interpretation](COMPARATOR_DECISION_OCT16.md)
- [Literature and contribution assessment](CONTRIBUTION_POSITIONING_OCT16.md)
- [Scientific audit](FINAL_SCIENTIFIC_AUDIT.md)
- [Release status and archive identities](RELEASE_STATUS_OCT16.md)

These are internal technical assessments and do not constitute external peer review. Their dates identify the evidence cutoff being assessed; later result reports may supersede a historical status statement.

## Integrity and recovery boundary

Checksums identify available committed bytes and do not imply that every referenced original archive exists. One original Letter archive container is still missing. The separately named replacement contains verified original payloads but is not asserted to have the original container identity. The release verifier preserves that distinction and its strict completeness mode reports the gap.

Recovery uses the selected store and surviving supported producers. Original capture archives are not a fallback source for omitted files. Roots, retained files and the recorded replay environment must satisfy the declared contract. Corruption, missing mandatory data and unsupported runtime changes are detected rather than silently bypassed.

The broad census's complete byte/source/ledger audit is `PYTHONPATH=src python scripts/audit_recovery_census_release.py results/research/recovery_census_oct26 --output work/new_census_audit.json`.
It materializes all original blocks, recomputes the full result and requires equality with the preserved verification-only cloud audit.
Use a fresh output path. The 100% DVC win rate applies to the fixed authored catalogue; it is not a production probability or a win over every recovery engine.

## Manuscript checkpoints

The repository retains dated drafts in `paper/` and `output/pdf/`. Result populations and implementation revisions are identified in their corresponding reports. Published-component adapters, manual retention controls, native DVC execution and the separately coded exact formulation are different comparator types and are labelled accordingly.
