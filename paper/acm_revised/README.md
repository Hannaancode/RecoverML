# RecoverML paper revision, 30 October 2026

`RecoverML_paper_revised.tex` is the editable ACM two-column manuscript. It was
revised from the author's 17 October LaTeX package and checked against the
later uploaded PDF titled *RecoverML: Exact Artifact Time Travel for ML
Pipelines under Declared Capability Loss*. The later PDF did not contain its
exact TeX source, so this revision preserves the packaged manuscript's
sections, figures, methods and references while matching the uploaded title,
author affiliation and email and adding the audited October 26-27 evidence.
The 30 October pass applies the author's writing rules throughout the prose,
shortens captions, adds a concise limitations section, uses the author-supplied
architecture diagram and adds the audited final runtime, independent-runner capacity and crash checks.
The compiled result is `../../output/pdf/RecoverML_paper_revised.pdf`.

The source folder contains the supplied `acmart.cls` and
`ACM-Reference-Format.bst`, seven used vector figures, the author-supplied
`methodology_user.png`, and scripts that rebuild all used figures. The four
historical charts read saved research ledgers, the Letter chart reads the
measured rows in `results/research/gigabyte_letter_oct16/summary.csv`, and the runtime chart
reads `results/research/runtime_scaling_oct30/evidence.zip`. The architecture
redraw follows the supplied image's layout and arrow directions.
The locally licensed Libertine/Biolinum fonts are also included. The
manuscript generates `references.bib` from its `filecontents` block.
The original 17 October source ZIP in Downloads also contains older plot inputs
and audit receipts. Those receipts describe the earlier cutoff and are not
claimed as checks of this revision. Current experiment ledgers are in the
repository's `results/research/` folders.

## Build

From the repository root, install the pinned Python package and run the single
rebuild command with Tectonic 0.17.0 and `pdfinfo` on the path:

```sh
python -m pip install -e .
python scripts/rebuild_revised_paper.py
```

This audits the permanent runtime and independent-runner archives, regenerates all seven used vector
figures from the saved ledgers or supplied architecture image, compiles the
paper and checks its 10–12 page range. To compile the packaged TeX directly,
run from this directory or upload it to Overleaf and select XeLaTeX:

```sh
tectonic RecoverML_paper_revised.tex --outdir ../../output/pdf
```

The one-command build completed locally and produced a 12-page PDF. The title page,
published-rule comparison, new storage results, DVC census, figures and
references were rendered and inspected.
The PDF was also checked for text extraction and unresolved citation markers.
Some TeX underfull box warnings remain in the narrow two-column layout;
the final inspected pages have no clipped content.
The clean Linux rebuild is run in `.github/workflows/rebuild-revised-paper.yml`.

## Evidence and rubric crosswalk

The historical Milestone 2 rubric audit at Git commit `5c08783` records four
categories. This paper points to the corresponding project evidence; the
instructor decides how the course rubric applies to the submitted paper.

| Rubric category | Evidence shown in the paper and repository |
|---|---|
| Implementation and authenticity, 35% | Sections 3-4 explain capture, exact retention, certificates and hash-checked recovery; source and tests are in `src/` and `tests/`. |
| Benchmark harness, 25% | Experimental Setup names complete workload grids, protocols, controls and repetitions; `scripts/` and `run_benchmarks.sh` contain runnable harnesses. |
| Trace data authenticity, 25% | Results distinguish actual requests from structural or repeated checks and cite saved raw ledgers under `results/research/`. |
| Preliminary plots and analysis, 15% | Seven vector figures and the complete storage table show comparisons, ties and limits. |

The rubric also asks for steady development across course weeks. Git history
contains the real commit dates; a paper revision cannot create earlier work.
The actual course screenshots were not included in this source package, so
this crosswalk uses the saved rubric audit rather than claiming a grade.

The 56-case published-rule comparison is recorded in
`results/research/paper_oct14/extension_analysis/measured_extensions.md`.
The independent-runner capacity study is in
`results/research/multi_runner_oct30/RESULTS.md`, with every request retained
in its archived GitHub artifact. The main new storage record is `results/research/solid_storage_oct27/RESULTS.md`
at source commit `efae825be13ffe487b915a4580cdc16b4c5e95c6`. The broad DVC
recovery record is `results/research/recovery_census_oct26/RESULTS.md`.
Their conditions are related authored workloads, not independent production
samples. Human course peer reviews have not been received.
