# Revised paper figure sources

Run the read-only source gate from the repository root:

```powershell
.venv/Scripts/python scripts/audit_paper_figure_sources.py
```

It fails when a plotted summary disagrees with the retained lower-level record. A passing gate verifies the saved evidence and figure inputs; it does not rerun model fitting, restore a missing original archive, or prove the experiment happened independently of the recorded artifacts.

| Figure | Plot input | Lower-level source checked by the gate | Check |
| --- | --- | --- | --- |
| Methodology | `paper/acm_revised/figures/make_methodology.py` | Author-supplied architecture sketch | Illustration, with no measured values |
| Shared storage | Three `strong_baseline_cloud_oct16/seed*/shared/summary.csv` files | Three `planner_records.json.gz` files | 972 planner repetitions; retained bytes and planning medians agree with 108 rows per seed; 36 plotted histories |
| Planner timing | `seed20261016/dag_timing/report.json` | `planner_calls.json.gz` | 720 calls, five per method and case; all 48 medians and speedup ratios recomputed |
| Native recovery | Three `native_frontier_cloud_oct16/v4/seed*/native_paired/raw_recovery.jsonl` files | Same trial records | 216 raw trials; complete three-repeat paired grid for 36 histories |
| Retinal storage | `eyeai_complete_oct15/summary.csv` | `captures/*/manifest.json`, `store_index.json.gz`, `planner_records.json.gz` | All 540 policy conditions recomputed from captured graph and physical selection; 216 rows feed the 108 plotted comparisons |
| Letter storage | `gigabyte_letter_oct16/summary.csv` and `analysis.json` | `manifest.json`, `planner_records.json`, `blob_inventory.json`, recovered frontier archive and source preflight archive | All 10 policy rows recomputed from recorded blob sizes; four reconstructed frontier payloads checked against SHA-256 and byte size |
| Runtime scaling | `runtime_scaling_oct30/evidence.zip` | Archived `trials.jsonl` | 252 raw trials in 84 complete three-repeat conditions |

The Letter study's original `results/research/gigabyte_letter_oct16/selected_frontier.tar.gz` is absent. The recovered `recovered_frontier_payloads.tar.gz` contains the four frontier payloads, manifest and failure contract; its contents match the archived hashes and sizes. It is a payload-equivalent reconstruction, not the original archive bytes. The gate reports the absence explicitly and will verify the original archive hash and members if that file is restored.
