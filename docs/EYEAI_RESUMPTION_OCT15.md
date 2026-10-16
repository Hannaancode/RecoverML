# Outcome-independent retinal resumption

The original run was stopped with exit 130 after 412 completed summary rows because its visible raw trace contained 5,593 records while the summary described 7,772 requests. The exact cause is unproven and no missing request timing is reconstructed. The unchanged interrupted directory and source hashes are preserved.

All nine logistic captures must pass the independent audit in `scripts/merge_eyeai_resume.py` before reuse. It checks the complete row and request identities and raw metrics and manifest and membership and payload hashes and planner entries and structural closure and native command receipts. The expected reusable subset contains 270 rows and 5,460 raw requests and 312 native DVC checkout commands.

All nine forest captures will be rerun using the already published source and unchanged experimental parameters. This includes completed forest cases rather than selecting successful outcomes. The fixed derivative configuration is `configs/eyeai_forest_resume_oct15.json`. It changes the estimator subset and expected subset counts and output location and clarifies that version settings are not literal nested prefixes. The full target remains 540 rows and 10,920 actual requests and 624 native checkout receipts used by the final grid. Additional checkouts from the discarded forest attempt will be counted separately.

Measurements write to `/tmp` outside the synchronized workspace and only closed files are copied back. The merger preserves excluded interrupted evidence in a separate archive and remaps native receipt IDs while retaining their original IDs. The final deduplicated archive contains exact retained payloads and every store membership and manifest.

Example commands from the repository root with the pinned environment active:

```bash
PYTHONPATH=src python scripts/merge_eyeai_resume.py --original results/research/eyeai_rebuild_oct15 --output /tmp/unused-eyeai-audit --audit-only
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m recoverml.eyeai_experiment --output /tmp/recoverml-eyeai-forest-resume --dataset work/stare --config configs/eyeai_forest_resume_oct15.json
PYTHONPATH=src python scripts/merge_eyeai_resume.py --original results/research/eyeai_rebuild_oct15 --rerun /tmp/recoverml-eyeai-forest-resume --output /tmp/recoverml-eyeai-complete
PYTHONPATH=src python scripts/analyze_eyeai.py /tmp/recoverml-eyeai-complete
PYTHONPATH=src python scripts/check_eyeai_frontier_formula.py /tmp/recoverml-eyeai-complete
PYTHONPATH=src python scripts/native_retina_repro.py --input /tmp/recoverml-eyeai-complete --output /tmp/recoverml-eyeai-native-control --capture forest_s3_v16
```
