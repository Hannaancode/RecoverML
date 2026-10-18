# Published evidence release status — 16 October 2026

This is a fresh-clone verification of the available research-branch release based on commit `cbd26d476d3c6313b456be7bd4bdc769ada637f7`, followed by documentation and verification-tool changes. Inspect the current branch head for the resulting commit. The manuscript/PDF at this cutoff is unchanged.

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

## Original evidence recovery update

Thirteen of the fourteen missing originals have now been recovered from the original capture workspace. Twelve match previously published SHA256 hashes exactly. The interrupted retinal archive had no previously published container hash and its newly observed SHA256 is recorded in `results/validation/2026-10-16/original_evidence_recovery/original_recovery_receipt.json`. Compressed stream integrity checks pass. No measurements or historical source files were rewritten.

The original 26 MB retinal payload archive exceeds the connector transport request limit. Its exact original bytes are published as seven parts listed in `docs/ORIGINAL_EVIDENCE_PARTS_OCT16.json`. The release checker verifies every part and then verifies the assembled bytes against the original full archive SHA256 `b088181bb0e57b266108fa188faeda549b3231834d517d4c7585593a93894e94`. This is a storage layout change and not a replacement of the original data.

After cloning this research branch run:

```bash
python scripts/materialize_evidence.py
```

This restores `results/research/eyeai_complete_oct15/stores_deduplicated.tar.gz` exactly for the existing retinal analyzer and restore tools. The checker can also verify the original bytes directly from committed parts without writing that file.

One original container remains unavailable:

- `results/research/gigabyte_letter_oct16/selected_frontier.tar.gz` with its historical SHA256 `0adf53f32d1e18b179ed7616acbf2408ddc9caa0dc3a634d671fcc3c410656c5`

All four frontier payload files were recovered from a preserved preflight archive and match the full study's recorded hashes and byte sizes. The full study manifest and failure contract are unchanged. They are published in the separately named `results/research/gigabyte_letter_oct16/recovered_frontier_payloads.tar.gz` with `frontier_recovery_receipt.json`. This is a verified payload-equivalent reconstruction and is explicitly not the original archive bytes. The original missing hash remains in the inventory. The original strict `--require-complete` check must therefore still report one unresolved original file. No fitted forest or execution timing was recreated for this repair.

The reconstruction is reproducible with `scripts/recover_letter_frontier.py` using the preserved source archive under `results/validation/2026-10-16/original_evidence_recovery`. Original available-file checks and checksum validation remain separate from complete original provenance.

## Remaining human/research inputs

External expert assessment, complete MinSS full-paper access and independently collected operational workflows remain outside the current evidence. Existing course concurrency traces and a second cloud environment do not establish multi-node scale-out or distributed crash consistency. No manuscript revision or formatting was performed.

Run `python scripts/verify_release.py --output work/release_check.json` from the repository root after committing. Run with `--require-complete` when testing whether the missing publication gap has actually closed. A successful available-evidence check is explicitly narrower than full release completion or payload replay.
