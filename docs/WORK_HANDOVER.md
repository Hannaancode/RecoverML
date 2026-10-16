# RecoverML continuation checklist and file map

Updated 16 October 2026 for Abdul Hannaan. Paper drafting and formatting remain deferred. This file records the state needed to continue in another conversation without reconstructing decisions from chat.

## What is complete

- The scientific matrix at `results/research/scientific_complete_oct16` passed independent reconciliation of 1920 conditions and 36480 actual requests with zero unexpected outcomes. Both exact formulations agree on all 48 compared minima. Strong local search matches those minima in all 48 full budget cases. Below that budget the exact complete recovery objective does not maximize partial coverage.
- The EyeAI inspired STARE study is at `results/research/eyeai_complete_oct15` despite completing on 16 October. All 540 rows and 10920 requests reconcile and all requests recover exactly. There are 624 native DVC checkout receipts. RecoverML beats simple greedy in 12 of 108 minimum storage comparisons and ties it in 96 and ties strong local search in all 108. The simple feature frontier formula also matches all 108 optima. These are constructed histories from 20 public images and not the private EyeAI dataset.
- The native retinal DVC control at `results/research/eyeai_complete_oct15/native_dvc_repro` recovers all 32 targets after the legacy source module is physically removed. Manually chosen DVC retention matches RecoverML at 2523881 common accounting bytes. The first failed forced frozen stage attempt is preserved and the corrected documented ordinary reproduction command succeeds.
- The fixed larger study at `results/research/gigabyte_letter_oct16` trained all 16 distinct forests on all 20000 UCI Letter Recognition rows. All 48 actual runtime requests recover exactly and all 32 native DVC target files match. Full payload hashes and compressed contents were checked. The final analyzer now passes after correcting its order sensitive comparison of version records and preserving its initial failure.
- Larger study preprocessing scope: snapshots 3669545821 bytes and exact store 4829269 bytes and saving 3664716552 bytes or 3.6647 decimal GB or 99.8684 percent. Actual gzip saving is 290607161 bytes or 290.61 decimal MB and does not reach one GB. Broad training and prediction loss requires full snapshots and saves zero canonical bytes. Exact preprocessing ties both robust heuristics. These outcomes must all be retained.
- Baseline sensitivity has 5760 structural conditions and component controls have 154 rows. A separate compact GitHub cloud reproduction has 192 conditions and 624 actual requests with zero unexpected outcomes. The expanded local CPU PyTorch suite passed 109 tests. See the scientific audit for their exact scopes.

## Repository and durable checkpoints

Repository: https://github.com/Hannaancode/RecoverML

Current research branch: `research/scientific-validation-oct15`

Last inspected remote head before this handover publication: `5c0878382723a2b6da0dded1d47212082da110f5`. Main still has the older Oct14 checkpoint and must not be assumed to contain today's files. This handover is being added on the research branch. Newer publication receipts take precedence over the checkpoint named here.

The research branch already contains the implementation and frozen scientific and retinal and larger study protocols and the UCI Letter input file and completed sensitivity and component and cloud evidence. Scientific full matrix text reports and receipts were added at 5c087838. Some new binary raw evidence and plots have not yet been attached to the branch. Local files existing or a Git object uploaded without a committed branch reference do not establish publication.

Local checkout: `/workspace/scratch/03a1fa6b3213/recoverml_git`. A new computer should clone the research branch using the guide rather than depend on this transient path.

## Remaining tasks and requirements

| Task | Work still required | Files or data needed | Availability at this checkpoint |
|---|---|---|---|
| Finish evidence publication | Commit raw traces and closed archives and plots and the latest analyzer and native control changes and verify every remote Git blob hash | The three result folders above plus `scripts/analyze_gigabyte_history.py` and `scripts/native_retina_repro.py` and validation receipts | Complete local files exist but not all new files are yet attached to GitHub |
| Finish final documentation | Update README and reproduction guide and research progress and the 24 task audit to the measured final state and regenerate checksum manifests | `README.md` and `reproducibility.txt` and `docs/reserach_progress.txt` and `docs/FINAL_SCIENTIFIC_AUDIT.md` and `CHECKSUMS*.json` | Draft updates are local and publication is being completed; old published guide may describe the previous checkpoint |
| Integrity review complete | Publish preserved analyzer failure and corrected checks and six deliberate corruption controls | `analysis_ordering_diagnosis.json` and `initial_analysis.json` in the larger study plus `scripts/audit_gigabyte_ledger.py` and `results/validation/2026-10-16/gigabyte_ledger_controls` | All six controls and the independent numeric and source and compact archive checks pass locally |
| Resolve scientific novelty and contribution strength | Obtain a full related work challenge and decide what is actually new and useful; the existing real workflows often admit simple optimal retention | `docs/NOVELTY_REVIEW_OCT15.md` and `docs/CONTRIBUTIONS_OCT15.md` and `docs/TRACTABLE_SUBCLASS_OCT15.md` and `docs/EYEAI_FRONTIER_ANALYSIS.md` plus new evidence if making a stronger claim | Core reviews are on the research branch and updated conclusions are local; full Collab and MinSS paper access and an external expert review remain unresolved |
| Obtain course peer review | Receive the two actual assigned peer reviews then answer each comment with the change and evidence | Two real peer review documents and a point by point response table | Not supplied and cannot be created by labelling AI audits as course peer reviews |
| Complete manuscript and formatting later | Revise claims and three defensible contributions and integrate final tables and plots then perform whole paper review and venue formatting | `paper/RecoverML_capability_loss.md` and `output/pdf/RecoverML_capability_loss.pdf` and final evidence and references | Existing draft and PDF are on GitHub and have intentionally not been revised in this phase |
| Check any remaining Milestone 4 scope | Confirm the required scale up and scale out and contention and crash invariants against what the system actually supports | Actual rubric and final architecture scope and any newly required workload | Rubric interpretation is recorded in the audit; no multi node scale out or distributed crash consistency result is claimed |

A large saving and exact recovery do not prove universal superiority or a new general optimization theory. The general finite contract has an explicit weighted positive Horn abduction encoding and a common single producer DAG subclass has a standard minimum cut solution. The three current contribution categories are the recovery contract and a checked exact implementation and an empirical storage versus recovery study. They are not three established independent theoretical inventions. Never promise acceptance or alter logs to force every method comparison into a win.

## Required inputs and where they live

| Input | Where to obtain it | Need the old conversation? |
|---|---|---|
| Prototype source and existing tests | `src/recoverml` and `tests` on GitHub research branch | No |
| Fixed experiment settings | `configs/scientific_audit_oct15.json` and resumption configs and `configs/eyeai_rebuild_oct15.json` and `configs/gigabyte_letter_oct15.json` | No; check the exact filenames in the reproduction guide |
| UCI Letter Recognition data | `data/letter_recognition/letter-recognition.data` on research branch with SHA256 `2b89f3602cf768d3c8355267d2f13f2417809e101fc2b5ceee10db19a60de6e2` and its attribution README | No |
| Public STARE images and masks | `scripts/download_stare.py` verifies the pinned public repository revision and source file hashes and writes `work/stare` | No; original image files are downloaded rather than committed individually |
| Old smaller scientific data | Public datasets loaded by the recipes and the pinned public sources recorded in protocols | No |
| Published comparison code | HYPPO pinned released components downloaded to a cache and documented HELIX rule implementation in the project | No; these are released component comparisons rather than complete native HELIX and HYPPO lifecycle replications |
| Large raw fitted model payloads | Local ignored `work/gigabyte_letter_oct16` while this workspace exists or regenerate from the fixed public data and protocol | No; the gigabytes of recomputable models are deliberately not committed; saved hashes and compact selected frontier and raw execution receipts are required in the release |
| New experiment raw execution evidence | The three closed result folders above; publication remains incomplete until remote hashes are checked | No once all evidence is published; before that a fresh clone alone is incomplete |
| Milestone 2 to 4 instructions | Required parts transcribed into `docs/FINAL_SCIENTIFIC_AUDIT.md` and earlier `docs/RUBRIC_AUDIT.md` | The original screenshots were provided in chat and are not repository inputs; keep copies for any wording omitted or cropped |
| Original 24 task request | Requirements and status captured in `docs/FINAL_SCIENTIFIC_AUDIT.md` | Original text is saved as docs/VALIDATION_REQUEST_OCT15.txt and the audit records its task list |
| Author preferences and next action | This handover: continue validation and publication and retain all results and defer manuscript work until author instruction | No |

No GPU is needed for the current CPU planners and forests. Linux or WSL2 with Python 3.12 and the eight pinned dependencies is the tested route. The existing compact cloud reproduction already supplies a second execution environment but not a full cross environment byte replay of the old saved models.

## First actions for the next session

1. Read this handover and the final scientific audit and inspect the actual research branch head and remote tree.
2. Check which raw evidence files are still missing remotely before repeating any experiment. Reuse only closed reconciled results and never infer lost timings.
3. Finish remaining upload and documentation and checksum checks before announcing full publication.
4. Retain the first failed native control and analyzer order mismatch as labelled superseded evidence.
5. Ask the author for paper drafting instructions only after giving an honest scientific readiness report and distinguish external peer review from implementation completion.
