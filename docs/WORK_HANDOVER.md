# RecoverML continuation checklist and file map

Latest completed follow-ups are permanently saved under:
- `results/research/strong_baseline_cloud_oct16`: all three seed blocks, 72 history/contract cases, 648 method rows, 1,944 planner calls, 216 flow proofs, and 19,652 actual requests (16,110 exact, 3,542 expected blocked, zero unexpected). Shared-loss storage: 9/36 wins over local search, 27 ties, maximum 48.7380%; all 18 combined-table controls and all 72 manual frontiers tie. Median paired local planning speedups: 11.92x separate, 16.88x shared.
- `results/research/native_frontier_cloud_oct16`: final v4 run 38953068522, runtime source f00981ea84357199f0bde6916a5536684b1ed567. Same optimal paid payloads as batched native DVC; 36/36 faster, 216 commands, 12,096 exact file checks. Median paired speedups: 2.1856x for 18 recomputation histories, 9.9067x for 18 fully retained histories. Cold CLI scope only.
- Superseded native v1/v2/v3 evidence and the first setup failure are preserved. Correct-cache v3 had 18 DVC wins for retained targets; the standard-library file export in v4 addresses that overhead. No pooling of development versions.
- Main now contains the research history with original commit dates; no history was fabricated or backdated. The final evidence commit is identifiable from Git history without embedding its own hash.
- Run both complete follow-up checkers from their RESULTS.md instructions. CI now rechecks both complete published grids.

These completed fresh reruns supersede the lost/partial-run statuses in historical notes below; they do not reconstruct missing old logs.
The comparison decision is in `docs/COMPARATOR_DECISION_OCT16.md`.
Human course reviews (zero assigned/completed), one original Letter archive-container gap, and manuscript integration remain open.
The payload-equivalent Letter reconstruction is checked separately; `release_complete` remains false.
No universal dominance, weighted overall winner or new general optimization theory is established.

Updated 16 October 2026 for Abdul Hannaan. Paper drafting and formatting remain deferred. This file records the state needed to continue in another conversation without reconstructing decisions from chat.

## What is complete

- The checked DAG exact engine and the complete first multiview grid are published. The first grid has 36 constructed histories and 324 method conditions and 12948 actual requests with zero unexpected outcomes. Strong local search ties 30 storage conditions and loses six by only 129 bytes. The manual frontier matches all 36 minima. Read `docs/STRONG_BASELINE_FOLLOWUP_OCT16.md` and the raw evidence at `results/research/multiview_followup_oct16`.
- The locally completed correlated-loss study and its later replay lost their unpublished files after chat resets. Earlier chat storage wins and timings must not be treated as a closed published study. Only the four-history prefix at `results/validation/2026-10-16/shared_loss_replay_checkpoints/closed_prefix_04.tar.gz` is published. It is partial evidence and not proof that the full grid finished.
- A durable complete rerun was launched from commit `00bd37a8addd6cea919edf2189c3246811bb669e`. GitHub Actions run https://github.com/Hannaancode/RecoverML/actions/runs/38945172079 has three fixed seed jobs. Each makes fresh captures on its own runner and evaluates both complete failure groupings under that recorded runtime. This avoids changing the environment contract of old captured models. Historical launch status: all three jobs subsequently finished and their artifact bytes, raw logs, captures and reports were copied into the repository and checked. See the completed follow-up above.

- The scientific matrix at `results/research/scientific_complete_oct16` passed independent reconciliation of 1920 conditions and 36480 actual requests with zero unexpected outcomes. Both exact formulations agree on all 48 compared minima. Strong local search matches those minima in all 48 full budget cases. Below that budget the exact complete recovery objective does not maximize partial coverage.
- The EyeAI inspired STARE study is at `results/research/eyeai_complete_oct15` despite completing on 16 October. All 540 rows and 10920 requests reconcile and all requests recover exactly. There are 624 native DVC checkout receipts. RecoverML beats simple greedy in 12 of 108 minimum storage comparisons and ties it in 96 and ties strong local search in all 108. The simple feature frontier formula also matches all 108 optima. These are constructed histories from 20 public images and not the private EyeAI dataset.
- The native retinal DVC control at `results/research/eyeai_complete_oct15/native_dvc_repro` recovers all 32 targets after the legacy source module is physically removed. Manually chosen DVC retention matches RecoverML at 2523881 common accounting bytes. The first failed forced frozen stage attempt is preserved and the corrected documented ordinary reproduction command succeeds.
- The fixed larger study at `results/research/gigabyte_letter_oct16` trained all 16 distinct forests on all 20000 UCI Letter Recognition rows. All 48 actual runtime requests recover exactly and all 32 native DVC target files match. Full payload hashes and compressed contents were checked. The final analyzer now passes after correcting its order sensitive comparison of version records and preserving its initial failure.
- Larger study preprocessing scope: snapshots 3669545821 bytes and exact store 4829269 bytes and saving 3664716552 bytes or 3.6647 decimal GB or 99.8684 percent. Actual gzip saving is 290607161 bytes or 290.61 decimal MB and does not reach one GB. Broad training and prediction loss requires full snapshots and saves zero canonical bytes. Exact preprocessing ties both robust heuristics. These outcomes must all be retained.
- Baseline sensitivity has 5760 structural conditions and component controls have 154 rows. A separate compact GitHub cloud reproduction has 192 conditions and 624 actual requests with zero unexpected outcomes. The expanded local CPU PyTorch suite passed 109 tests. See the scientific audit for their exact scopes.

## Repository and durable checkpoints

Repository: https://github.com/Hannaancode/RecoverML

Current research branch: `research/scientific-validation-oct15`

The fresh-clone continuation started at `cbd26d476d3c6313b456be7bd4bdc769ada637f7`, which added all three raw request logs after this handover's first version. Inspect `git rev-parse HEAD` on the research branch for the documentation/verification follow-up. This was the original continuation checkpoint; main has since been advanced to include the research history and today's work.

The research branch contains implementation, frozen protocols, the UCI Letter input, sensitivity/component/cloud evidence, final scientific/retinal/Letter reports, and all three raw request logs. Publication is still incomplete: the exact missing original archives and files are listed in [release status](RELEASE_STATUS_OCT16.md). Local files or unreferenced Git objects do not establish publication. The new verification scripts check committed Git bytes, so Windows newline conversion cannot silently change the identity being audited.

Original capture workspace: `/workspace/scratch/03a1fa6b3213/recoverml_git`. It was revisited for this recovery and supplied thirteen original files and the four recorded Letter frontier payloads from a preserved preflight. Clone the research branch using the guide; do not assume either transient path is available on another host.

## Completed in the fresh-clone continuation

- Independently parsed all 36,480 scientific, 10,920 retinal and 48 Letter raw requests. Frozen scientific conditions and headline outcome counts reconcile, and the complete retinal fault/version request grid and summary counts reconcile.
- Verified all available original scientific SHA256SUMS entries and all 56 frozen Letter source hashes from exact Git object bytes.
- Re-executed the existing retinal analyzer and Letter structural analyzer on disposable copies, checked Letter numeric cross-links, and repeated all six ledger mutation controls. They pass; all original input files remain unchanged. Results and regenerated plots are saved at `results/validation/2026-10-16/release_recheck`.
- Added `scripts/verify_release.py` and six regression tests for corruption/duplication/omission detection. Refreshed both available-release checksum manifests, preserving the original October14 manifests in `docs/history`. The check refuses mismatched/unlisted published bytes. `--require-complete` deliberately fails while original required evidence remains absent.
- Corrected stale large-study/native-control statements in the final audit and guide. Collab full-text Sections4â€“6 are now reviewed in `docs/NOVELTY_REVIEW_OCT15.md`; MinSS full text and external review remain open.

This is ledger, source and byte verification on Windows/Python3.12.8 with pinned numerical/plotting packages. Models were not retrained or replayed and native DVC was not rerun. The original scientific manifest-derived audit and compact payload verification still require missing archives. Manuscript and PDF work remain deferred.

## Remaining tasks and requirements

| Task | Work still required | Files or data needed | Availability at this checkpoint |
|---|---|---|---|
| Finish original evidence publication | Recover the missing historical archives/summary/figures and verify their recorded hashes before publishing | Exact paths in `docs/RELEASE_STATUS_OCT16.md` and `scripts/verify_release.py`; original capture workspace | Thirteen missing originals recovered and published with original retinal archive bytes verified from transport parts. One original Letter frontier container is still missing and a separately named four-payload hash-matched reconstruction is available. The original expected archive hash remains unchanged |
| Available-release documentation and checksums | Complete for the checked scope; regenerate checksums again after any subsequent tracked edit | README, guide, progress, final audit, release status, handover, both checksum manifests | Updated with current measured results and explicit incomplete-publication scope. Historical checksum manifests preserved. Use `python scripts/verify_release.py` on the final commit |
| Published-ledger integrity | Complete for available numerical/structural ledgers; compact payload audit still awaits the missing frontier | `results/validation/2026-10-16/release_recheck`, original `gigabyte_ledger_controls_v3`, new verification scripts/tests | Six mutation controls and numerical/source checks freshly pass; missing payload archive is explicitly not verified. Original analyzer failure remains preserved |
| Contribution positioning | Internal positioning decision and whole-project scientific review completed; external novelty confirmation remains open | `docs/CONTRIBUTION_POSITIONING_OCT16.md`, `docs/INTERNAL_REVIEW_OCT16.md`, contribution scorecard and primary-source register | Lead with auditable preservation contract, checked implementation and measured tradeoffs. Strong local search ties 48/108/2 full-contract comparisons;25/27 captures meet the sufficient tractable subclass. MinSS full text and external expert review remain unresolved |
| Obtain genuine course peer review | Obtain the actual course allocation/instructions and real reviewer work/comments, then answer real comments point by point | `docs/COURSE_PEER_REVIEW_PACKET.md`, `docs/COURSE_PEER_REVIEW_TRACKER.json`, actual assignment and original human reviews | Author explicitly reported no assigned reviewers/comments on 16 October. Packet prepared; zero genuine reviews completed and no outreach sent. Distinguish reviews the student must write from feedback received |
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
| Milestone 2 to 4 instructions | Required parts transcribed into `docs/FINAL_SCIENTIFIC_AUDIT.md` and earlier `docs/RUBRIC_AUDIT.md` | Original screenshots or instructor clarification are still needed for omitted/cropped wording and acceptance decisions |
| Original 24 task request | Requirements and status captured in `docs/FINAL_SCIENTIFIC_AUDIT.md` | Original text is saved as docs/VALIDATION_REQUEST_OCT15.txt and the audit records its task list |
| Author preferences and next action | This handover: continue validation and publication and retain all results and defer manuscript work until author instruction | No |

No GPU is needed for the current CPU planners and forests. Linux or WSL2 with Python 3.12 and the eight pinned dependencies is the tested route. The existing compact cloud reproduction already supplies a second execution environment but not a full cross environment byte replay of the old saved models.

## First actions for the next session

1. Read this handover, release status and final scientific audit; inspect the actual research branch head.
2. Run `python scripts/verify_release.py --output work/new_release_check.json`. A passing available-file audit is narrower than complete release publication. `--require-complete` must still fail until every original gap is resolved.
3. Recover missing originals from the capture workspace or obtain an author-supplied archive. Check hashes before upload. Repeat no completed experiment merely because an unpublished archive is missing; a genuinely fresh rerun must have new identities and measurements.
4. Retain the first failed native control and analyzer order mismatch as labelled superseded evidence.
5. Ask the author for paper drafting instructions only after giving an honest scientific readiness report and distinguish external peer review from implementation completion.

## Subsequent original workspace recovery

Read RELEASE_STATUS_OCT16.md for the current repair. Thirteen originals are restored and a payload-equivalent Letter frontier archive is available under its explicit new name. The strict original-container gap is now one file rather than fourteen. Run scripts/materialize_evidence.py after clone to reconstruct the byte-identical retinal archive from its committed parts. Both old original archive identities and all existing measurements remain unchanged.

## Contribution and course-review follow-up

The final evidence base at 85a086b was reviewed without revising the manuscript or measurement files. `scripts/audit_contribution_evidence.py` produces `results/validation/2026-10-16/contribution_review/verified_scorecard.json`. It confirms 6/8 scientific,18/18 retinal and1/1 Letter captures meet the sufficient single-producer-DAG condition. It reconciles all 48 scientific,108 retinal and 2 Letter exact/local-search ties, and 12 retinal improvements over simple greedy. Input identity checks distinguish Git bytes from checkout newline conversions. Five classifier/duplicate-condition regression tests pass.

The recommended contribution is auditable retention automation with an explicit conditional recovery contract and empirical boundaries, not a newly established general optimization theory or universal performance win. The new review includes the later 2025 Hyppo publication and keeps full MinSS access and external expert review pending. The author confirmed there are no assigned course reviewers/comments. A neutral packet and separate activity tracker are prepared; human reviews must not be marked complete until the actual course process supplies them. Paper drafting/formatting remains deferred.
