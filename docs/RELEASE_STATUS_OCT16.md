# Published evidence release status — 16 October 2026

This is a fresh-clone verification of the available research-branch release based on commit `cbd26d476d3c6313b456be7bd4bdc769ada637f7`, followed by documentation and verification-tool changes. Inspect the current branch head for the resulting commit. Manuscript/PDF work remains deferred.

## Completed bounded checks

- Parsed every published raw request: 36,480 scientific, 10,920 retinal and 48 large-study records. Scientific condition identities, outcome partitions, report totals and per-method headlines reconcile; retinal declared request identities and 540 summary rows reconcile.
- The scientific raw log matches its recorded SHA256. Every available file in its original SHA256SUMS list matches. All 56 frozen large-study sources match their recorded hashes using exact Git bytes.
- Re-executed the existing retinal analyzer and large-study structural/numerical analyzer on temporary copies. All checks passed. The large-study numeric cross-links and all six deliberate ledger mutation controls passed. All original input files remained unchanged. This run used Windows/Python 3.12.8 and the pinned numerical/plotting packages; it did not benchmark recovery on Windows.
- New plots are regenerated from existing records under `results/validation/2026-10-16/release_recheck`. They are new renders, not recovered originals. No missing source summary or historical timing is reconstructed.
- Refreshed both top-level checksum manifests to cover the exact staged/committed bytes of all tracked regular files, excluding only the two manifests. Historical October14 manifests remain in docs/history. `scripts/verify_release.py` fails on byte mismatches, unlisted files, or ledger inconsistency; `--require-complete` additionally rejects the known incomplete release.
- Six regression tests demonstrate rejection of fixed-count duplicate requests, altered raw bytes, altered frozen source, omitted checksum entries, and missing archives.

## Measured study outcomes

| Study | Published result | Qualification |
|---|---|---|
| Scientific | 1,920 conditions; 36,480 requests; 15,420 exact and 21,060 expected blocked; zero unexpected | Strong local search ties all 48 full-budget minima. Original manifest-derived reanalysis needs missing archives. |
| Retinal | 540 rows; 10,920 exact requests; 624 native DVC checkout receipts | Strong local search and simple frontier tie all 108 optima; three seed blocks reuse 20 images. |
| Native retinal pipeline | 32 exact targets after physical legacy-code retirement | Manual DVC frontier ties 2,523,881 common bytes. Receipts checked; DVC execution not repeated here. |
| Letter preprocessing | 3,669,545,821 snapshot bytes minus 4,829,269 retained bytes = 3,664,716,552 bytes saved | 99.8684% canonical saving; gzip saving 290,607,161 bytes, below one GB compressed. Heuristics tie. |
| Letter broad loss | Zero canonical/gzip saving | Training/prediction loss requires snapshots. 48 actual runtime requests cover three shared stores; broader cases are structural checks. |

## Incomplete original publication

These required original files are absent from the audited branch. Known expected hashes are preserved in the original receipts and in the release inventory. Do not remove an expected file from the inventory merely to obtain a passing completeness status.

- `results/research/eyeai_complete_oct15/planner_records.json.gz`
- `results/research/eyeai_complete_oct15/store_index.json.gz`
- `results/research/eyeai_complete_oct15/stores_deduplicated.tar.gz`
- `results/research/gigabyte_letter_oct16/selected_frontier.tar.gz`
- `results/research/scientific_complete_oct16/accepted_case_evidence.tar.gz`
- `results/research/scientific_complete_oct16/captures.tar.gz`
- `results/research/scientific_complete_oct16/common_budget_coverage.png`
- `results/research/scientific_complete_oct16/planner_records.json.gz`
- `results/research/scientific_complete_oct16/sensitivity.json.gz`
- `results/research/scientific_complete_oct16/source_versions.tar.gz`
- `results/research/scientific_complete_oct16/storage_recovery_tradeoff.png`
- `results/research/scientific_complete_oct16/summary.csv`
- `results/research/scientific_complete_oct16/superseded_attempts.tar.gz`
- `results/research/eyeai_complete_oct15/interrupted_attempt_evidence.tar.gz`

The interrupted retinal archive has no published expected hash; its name comes from the saved merger source. Obtain it from the original capture workspace before asserting that superseded attempts are fully preserved. Full fitted Letter payloads are deliberately not committed and are a separate fresh-regeneration input.

## Remaining human/research inputs

External expert novelty review, genuine course peer reviews and their actual comments, complete MinSS full-paper access, independent operational workflows if claiming optimization necessity, and missing/cropped rubric wording remain unresolved. Existing course concurrency traces and a second cloud environment do not establish multi-node scale-out or distributed crash consistency. No manuscript revision or formatting was performed.

Run `python scripts/verify_release.py --output work/release_check.json` from the repository root after committing. Run with `--require-complete` when testing whether the missing publication gap has actually closed. A successful available-evidence check is explicitly narrower than full release completion or payload replay.
