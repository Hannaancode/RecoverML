# RecoverML — Milestone 2

RecoverML helps a machine learning pipeline save space and restore earlier versions of its work

For setup and checks and fresh experiments read the [complete reproduction guide](reproducibility.txt)
It explains Linux and Windows with WSL2 and installation and every run from start to finish
The complete saved evidence is on GitHub and the [publication record](docs/PUBLICATION_OCT14.json) records the verified upload

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
The twelve version study saves about 23.64 percent in the lossless cases and a separate disk only audit reproduces every equal budget outcome across 702 attempts
The new planner also passes generated cycle checks with up to 3073 nodes and the research suite includes 57 test cases with optional PyTorch checks
Read the [new research note](docs/WITNESS_PLANNER_AND_PIPELINES.md) for the experiments and the proof and the next steps

## Latest paper work

Our idea is to keep the smallest shared set of files that protects every required old model and prediction after any allowed tool loss
The new planner uses exact physical graph reduction and certified solving and checks every recovered result against its captured bytes

The final published method study has 28 histories and 56 cases and 33440 real requests
RecoverML restores all 3344 requests and HYPPO rank restores 2240 and HYPPO frequency restores 2291 at the same limits
The best tested common budget HELIX rule setting restores 1940 and all tested main methods recover every no outage request in the lossless subset
HYPPO uses unchanged released components and HELIX uses our documented published rule implementation and both use the common recovery executor

One shared graph protects 112 old versions and saves 93.50 percent of target snapshot bytes with one declared preprocessing loss and 83.94 percent with two
The layered study completes 9288 exact recoveries and the broader fitting and prediction outage study completes all 3920 requests exactly
The final suite has 77 tests with 72 passing and five optional PyTorch checks skipped

Our three contributions are a clear minimum storage recovery contract and an exact physical optimizer and a reproducible study of the price of stronger recovery
Read the [full project summary in simple words](docs/PROJECT_SUMMARY.md) and [current paper](paper/RecoverML_capability_loss.md) and [paper PDF](output/pdf/RecoverML_capability_loss.pdf)
The [saved paper evidence](results/research/paper_oct14/README.md) contains the logs and source versions and selected stores and figures
The next plan is independent reproduction and expert novelty review and a selected venue format after the author reads the paper

## Earlier capability loss checkpoint

The new planner saves enough files before replay tools become unavailable and protects every old model and prediction after any allowed combination of tool outages
It tries to break a small store with an allowed outage and learns which extra files must be saved and repeats until recovery is certified
Two recorded tools can rebuild the same feature bytes so the planner can keep small shared files and still recover every protected version

Our three contributions are a clear recovery contract for tool outages and a minimum storage planner that learns from failing cases and a reproducible study of storage savings with exact recovery
The complete new Banknote study restored all 792 requests with the new method
With lossless features and at most one tool group outage the store saved 43.24 percent compared with full target snapshots and 34.04 percent compared with the minimum store for losing all declared tools
The three seed one outage condition completed 144 exact recoveries and the two outage and rounded CSV controls show when a larger store is needed
The complete test suite has 63 tests with 58 passing and five optional PyTorch checks skipped in this environment
Read the [idea and three contributions and literature comparison](docs/CAPABILITY_LOSS_NOVELTY.md) and the [saved raw evidence](results/research/capability_loss_oct13/README.md)
The literature comparison defines the specific proposed novelty and the next paper checks

## Start here

| What you need | Where to look |
|---|---|
| Instructor review and reproduction | [Submission guide](docs/SUBMISSION.md) |
| Complete setup and reproduction steps | [Reproduction guide](reproducibility.txt) |
| Evidence for each rubric requirement | [Rubric checklist](docs/RUBRIC_AUDIT.md) |
| All experiments and their files | [Results guide](results/README.md) |
| Latest throughput and latency analysis | [Performance report](docs/reports/PERFORMANCE_REPORT.md) |
| Storage coverage and planner comparison | [Iteration 2 report](docs/reports/ITERATION2_REPORT.md) |
| How the planner works | [Planner design](docs/PLANNER_V2.md) |
| Exact frontier rule and proof | [Frontier reduction](docs/FRONTIER_REDUCTION.md) |
| Focused novelty comparison | [Novelty audit](docs/NOVELTY_AUDIT.md) |
| Current research paper | [Paper draft](paper/RecoverML_capability_loss.md) and [Paper PDF](output/pdf/RecoverML_capability_loss.pdf) |
| Full project explanation | [Simple project summary](docs/PROJECT_SUMMARY.md) |
| Earlier milestone paper | [Milestone draft](paper/RecoverML_draft.md) and [Milestone PDF](output/pdf/RecoverML_paper.pdf) |
| Research sources for the next stage | [References](docs/REFERENCES.md) |
| Latest code improvements | [8 October progress](docs/history/PROGRESS_OCT8.md) |
| Current experiments and research decisions | [Research progress](docs/reserach_progress.txt) |
| Alternative artifact recovery and storage planning | [New recovery experiments](docs/WITNESS_PLANNER_AND_PIPELINES.md) |
| Recovery after replay tool outages and three contributions | [New paper direction](docs/CAPABILITY_LOSS_NOVELTY.md) |
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
CHECKSUMS_GITHUB.json checks the currently published files and the complete local package also keeps every saved evidence archive
The GitHub Actions workflow runs correctness checks and a smoke experiment on every push

## Run the project

Use Python 3.12 and Linux or WSL for CPU and memory tracing

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e '.[paper]'
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

For the current paper matrix run the following with a new output folder

```bash
bash scripts/run_paper_benchmarks.sh results/runs/my_paper_reproduction
```

The [reproduction guide](reproducibility.txt) includes package checks and saved figure regeneration and a small first run and the full matrix and what to compare
Fresh runs capture their own environment and strict replay of archived stores also needs their full recorded environment

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
