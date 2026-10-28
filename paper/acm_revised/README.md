# RecoverML paper revision, 28 October 2026

`RecoverML_paper_revised.tex` is the editable ACM two-column manuscript. It was
revised from the author's 17 October LaTeX package and checked against the
later uploaded PDF titled *RecoverML: Exact Artifact Time Travel for ML
Pipelines under Declared Capability Loss*. The later PDF did not contain its
exact TeX source, so this revision preserves the packaged manuscript's
sections, figures, methods and references while matching the uploaded title,
author affiliation and email and adding the audited October 26-27 evidence.
The compiled result is `../../output/pdf/RecoverML_paper_revised.pdf`.

The source folder contains the unmodified `acmart.cls` and
`ACM-Reference-Format.bst` supplied in the author's package, plus its seven
original vector figures and locally licensed Libertine/Biolinum fonts. The
manuscript generates `references.bib` from its `filecontents` block.
The original 17 October source ZIP in Downloads also contains older plot inputs
and audit receipts. Those receipts describe the earlier cutoff and are not
claimed as checks of this revision. Current experiment ledgers are in the
repository's `results/research/` folders.

## Build

Run from this directory with Tectonic 0.17.0:

```sh
tectonic RecoverML_paper_revised.tex --outdir ../../output/pdf
```

The build completed locally and produced a 13-page PDF. The title page, new
storage results, DVC census, figures and references were rendered and inspected.
The PDF was also checked for text extraction and unresolved citation markers.
Some TeX underfull box warnings remain in the narrow two-column layout;
the final inspected pages have no clipped content.

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

The main new storage record is `results/research/solid_storage_oct27/RESULTS.md`
at source commit `efae825be13ffe487b915a4580cdc16b4c5e95c6`. The broad DVC
recovery record is `results/research/recovery_census_oct26/RESULTS.md`.
Their conditions are related authored workloads, not independent production
samples. Human course peer reviews have not been received.
