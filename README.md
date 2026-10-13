# RecoverML — Milestone 2

RecoverML helps a machine learning pipeline save space and restore earlier versions of its work

It records the data and model files and the links between them and stores identical parts once
The planner chooses what to keep within a storage budget and restores old models and predictions from saved files or recorded steps
Every loaded or rebuilt artifact is checked against its original SHA-256 fingerprint

## What we have achieved

We built a working Python prototype and an automated benchmark and faster version 2 and version 3 and version 4 planners
The storage study tested 11200 requests across 80 histories and version 2 restored all 1175 admitted requests exactly
On matched feasible histories planning was 19.3 times faster than version 1 and planning plus five restores was 3.4 times faster
The worker experiment restored all 5400 requests exactly and recorded real times and CPU and memory use
The new public data study tested 3600 requests across 24 Digits and Wine histories and version 3 restored all 535 admitted requests exactly
Version 3 reduced the opaque solver model from 129 variables to 98 and its repeated planner study measured a 1.18 times median history speedup over version 2
The new Iris scaling study used 15 histories and version 4 reduced a depth 128 model from 1256 variables to 69 while keeping every proven optimal objective unchanged
The same study measured a 3.38 times median history speedup over version 2 and completed 120 exact restores
The CPU neural study used the real Digits data and a multilayer neural network and completed 630 recovery requests with no unexpected failures
At a 50 percent storage budget version 4 restored all 18 requested outputs while full snapshots restored none and full replay restored 9
The wide graph study reached 1038 nodes and 1068 edges and all 315 planner runs kept the same proven optimal result
Version 4 used 98.21 percent fewer variables at the median and was 10.47 times faster than version 2 at the median
The PyTorch study adds a CNN for Digits images and a Transformer for real 20 Newsgroups text and restores all 48 admitted version 4 requests exactly
The same study checks 24 native model checkpoints and the 50 percent budget restores 18 of 24 requests while target snapshots restore 6
The new placement study uses 45 histories and 1215 planner runs and 135 exact restores and explains where the frontier improves planning
The earlier milestone suite has 49 passing automated tests and the raw measurements and plots are included

## New recovery experiments

The separate research branch adds a minimum storage planner and tests full model and prediction recovery when a legacy import step is unavailable
It can use another recorded step that produced the same bytes and checks every rebuilt file
The lossless feature import study saves about 17.86 percent of total storage across three public datasets and the rounded CSV control keeps the original recovery rule
The new planner also passes generated cycle checks with up to 3073 nodes and the research suite includes 57 test cases with optional PyTorch checks
Read the [new research note](docs/WITNESS_PLANNER_AND_PIPELINES.md) for the experiments and the proof and the next steps

## Start here

| What you need | Where to look |
|---|---|
| Instructor review and reproduction | [Submission guide](docs/SUBMISSION.md) |
| Evidence for each rubric requirement | [Rubric checklist](docs/RUBRIC_AUDIT.md) |
| All experiments and their files | [Results guide](results/README.md) |
| Latest throughput and latency analysis | [Performance report](docs/reports/PERFORMANCE_REPORT.md) |
| Storage coverage and planner comparison | [Iteration 2 report](docs/reports/ITERATION2_REPORT.md) |
| How the planner works | [Planner design](docs/PLANNER_V2.md) |
| Exact frontier rule and proof | [Frontier reduction](docs/FRONTIER_REDUCTION.md) |
| Focused novelty comparison | [Novelty audit](docs/NOVELTY_AUDIT.md) |
| Current integrated paper | [Paper draft](paper/RecoverML_draft.md) |
| Readable paper with tables and plots | [Paper PDF](output/pdf/RecoverML_paper.pdf) |
| Research sources for the next stage | [References](docs/REFERENCES.md) |
| Latest code improvements | [8 October progress](docs/history/PROGRESS_OCT8.md) |
| Current experiments and research decisions | [Research progress](docs/reserach_progress.txt) |
| Alternative artifact recovery and storage planning | [New recovery experiments](docs/WITNESS_PLANNER_AND_PIPELINES.md) |
| Full paper readiness and remaining work | [Paper status](docs/PAPER_STATUS.md) |

## Project layout

| Folder | Purpose |
|---|---|
| src/recoverml | Working capture and planning and restoration code |
| tests | Correctness and trace validation and runner tests |
| configs | Settings for smoke and performance and earlier experiments |
| scripts | Packaging and extra latency analysis tools |
| examples | Complete small captured history for replay |
| docs | Submission guide and rubric checklist and design and reports |
| results/milestone2 | Current performance and storage evidence and plots |
| results/archive | Earlier experiments and their complete submitted logs |
| results/validation | Dated test logs and later audit checks |
| results/research | Separate new recovery experiments and their raw evidence |
| results/runs | New local runs created by the runner and excluded from Git |

CHECKSUMS.json records the SHA-256 values for submitted files
The GitHub Actions workflow runs correctness checks and a smoke experiment on every push

## Run the project

Use Python 3.12 and Linux or WSL for CPU and memory tracing

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
bash run_benchmarks.sh
```

The runner tests three policies at two data sizes and 1 and 2 and 4 workers and repeats each setting three times
It creates a new folder under results/runs and saves tests and storage checks and performance logs and plots
Use an explicit new folder when needed

```bash
bash run_benchmarks.sh results/runs/my_experiment
```

An existing folder is refused before any tests start so earlier evidence stays unchanged
An ordinary CPU computer or Linux VM is enough

## Review the supplied evidence

```bash
PYTHONPATH=src python -m recoverml.performance --audit-only --out results/milestone2/performance
PYTHONPATH=src python -m recoverml.audit results/milestone2/storage
```

![Throughput across worker counts](results/milestone2/performance/throughput_vs_concurrency.png)

![Service latency CDF](results/milestone2/performance/latency_cdf.png)

The results guide links the earlier storage and planning plots and every raw log group
The performance report explains queue wait and slower cases and measurement scope

## Replay an example

```bash
recoverml select examples/captured_history --budget-bytes 2000000 --out work/retained
recoverml restore work/retained --version 0 --out work/restored_v0
```

The example records its original environment and restoration checks that environment
A fresh local benchmark captures histories using the installed environment

## Next plan

Repeat the main timing study on another machine and compare the measured results
Add larger real workflow graphs and measure how load costs affect planning
Ask an independent reviewer to challenge the novelty table and reproduce the main experiment
Turn the current paper draft into the selected venue format and connect every claim to its evidence
The earlier configurations and reports and raw measurements remain available for this work

[Public repository](https://github.com/Hannaancode/RecoverML)

## Run the PyTorch studies

Install the pinned CPU package and prepare the text dataset once and then run the automated study

```bash
python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
python -c "from sklearn.datasets import fetch_20newsgroups; fetch_20newsgroups(subset='all', remove=('headers','footers','quotes'))"
make pytorch-study
make boundary-controls
make oracle-audit
```

The checkpoints contain trained weights and model settings and the loader checks exact predictions
The research progress file records the experiments and the completed checks
