# Start here for drafting on 17 October

## Our idea in simple words

Researchers make many versions of an experiment and each version creates files
such as processed data and trained models and predictions. Keeping every file
uses space. Deleting too much can make an old result impossible to recover
when an old processing step no longer works.

RecoverML records how the files were made and which processing steps may stop
working. It then chooses files to keep so that the protected old results can
still be recovered. It checks the recovered files against their recorded
hashes. This guarantee uses the recorded dependencies and supported runtime
and the declared failure rules.

We have a working system and checked experiments. The new study shows that
shared processing failures can make a strong local-search choice use more
space than our exact choice. It also shows that recording a shared intermediate
file can remove this gap. A manually selected optimal frontier still matches
our storage. The paper should explain these choices and their costs clearly.

## What is ready

Read these in order:

1. [Claims and three contributions](CLAIMS_AND_CONTRIBUTIONS.md)
2. [Verified results tables](RESULTS_TABLES.md)
3. [Section outline and figure plan](OUTLINE.md)
4. [Citation map](CITATION_MAP.md)

The machine-readable files include [all 72 paired storage cases](cloud_storage_cases.csv),
[all 648 method rows](cloud_methods.csv), [method summaries](cloud_method_summary.csv),
[all 48 earlier planning-time cases](planner_timing_cases.csv) and a
[combined summary](results_summary.json). The [source manifest](evidence_manifest.json)
records exact source hashes and the [fresh audit receipt](audit_receipt.json)
records the independent evidence check done during preparation.

This folder prepares the next writing session. The manuscript at
[RecoverML_capability_loss.md](../../paper/RecoverML_capability_loss.md) and the
older [RecoverML_draft.md](../../paper/RecoverML_draft.md) have not been revised
by this preparation. Their cutoff hashes are in the manifest. Existing draft
headlines may be older than this folder's verified tables. Formatting and final
wording wait for the user's reading and instructions.

## Keep the parallel research work safe

This preparation lives on **`writing/preparation-2026-10-17`**, starting from
research commit **`e0c745a754599e45562067197da76ea7de0dd0e5`**. The active
**`research/scientific-validation-oct15`** branch belongs to the ongoing
baseline work. Preparation adds its own folder and one table-building script
and refreshes the checksum manifests. It does not change the benchmark code,
raw studies, manuscript or research-branch pointer.

The new native DVC batch **v2** results are **pending at this evidence cutoff**.
Do not read an older status as the latest live experiment result. Tomorrow,
inspect the current research branch before drafting. If it has new results,
record their commit and source commit and verify them before adding claims.
Do not pool baseline v1 and v2 or count failed setup runs as DVC losses.

## Tomorrow's order of work

1. Fetch the latest research branch and inspect the changes since the cutoff.
   Keep any in-progress local work intact and use a separate worktree if needed.
2. Check whether native DVC v2 has completed the full 36-history grid and all
   three paired repetitions per history. Require raw trials, command logs,
   environment records, exact target checks and both methods' failures.
   Report slower cases as well as faster ones. Keep smoke trials out of totals.
3. If the results are admissible, add a separate native-latency table with
   subprocess wall time and worker time kept separate. If the run is incomplete,
   keep it pending and draft from the already checked evidence.
4. Review the three contributions and decide the paper's scope with the user.
   Write methods and results first and the abstract last. Follow the outline
   and keep every numerical statement attached to a table or source report.
5. Recheck references and the identified related-work gap. Distinguish internal
   AI checks from human peer review. Verify the instructor or target venue's
   exact page and formatting rules before formatting.
6. After integrating newer research, regenerate the checksums against the
   combined tree. Do not copy this branch's older root checksum files over the
   newer research files without regenerating them.

## Recheck this frozen pack

From the repository root in Python 3.12, the table check needs only the standard
library and Git:

```bash
python scripts/prepare_drafting_bundle.py --check
python scripts/verify_release.py
```

The first command extracts the pinned source commit and verifies that all six
generated files match. It does not read future branch changes or run models.
The release audit checks tracked bytes and recorded ledgers. Its current
expected result is `available_evidence_checks: PASS` and
`release_complete: false`, because one original Letter archive container is
still missing. It must not be relabelled as a complete original release.

To repeat the deeper cloud audit, follow the environment installation in
[reproducibility.txt](../../reproducibility.txt), then run:

```bash
PYTHONPATH=src python scripts/audit_cloud_followup.py \
  results/research/strong_baseline_cloud_oct16 \
  --source-commit 00bd37a8addd6cea919edf2189c3246811bb669e \
  --output work/drafting_cloud_recheck_fresh.json
```

Use a new output filename if it already exists. This reconciles recorded cloud
evidence and checks proofs and archives. It does not retrain the models or
measure another performance trial. The full Linux or WSL2 benchmark setup and
rerun commands remain in the main reproducibility guide.

## Remaining decisions before submission

The existing evidence supports writing a scoped systems and empirical paper.
Global novelty and acceptance are not guaranteed. The closest MinSS full-text
comparison and independent expert challenge remain open. Genuine course peer
reviews require actual assignments and reviewers. Production prevalence of
the declared failure conditions and deployment effort have not been measured.
The original missing Letter container remains disclosed even though its four
recovered payloads match their original hashes. These are separate from the
completed cloud evidence checks and should have separate status in the paper.
