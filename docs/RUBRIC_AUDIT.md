# Milestone 2 rubric evidence — updated 9 October 2026

We have all four rubric screenshots and this table links each requirement to evidence
This is a submission checklist and the instructor decides the grade

| Rubric | Weight | Evidence |
|---|---:|---|
| Implementation and authenticity | 35% | Modular Python capture and graph and retention and exact disk restore code in src/recoverml and 33 passing tests in results/validation/2026-10-09/tests.txt |
| Benchmark harness | 25% | bash run_benchmarks.sh runs the main rubric matrix and make new-data-repeated runs 24 public-data histories with six budgets and five policies and no manual policy switching |
| Trace data authenticity | 25% | The main performance files include timestamps and latency percentiles and CPU and memory data and the new study adds 3600 request rows and 10030 audited trace events |
| Preliminary plots and analysis | 15% | The throughput and latency plots compare baselines and the new success and opaque coverage plots compare five policies and the V3 ablation plot shows paired planner timing |

All new experiment files are in results/milestone2
The performance audit passed for 5400 requests and 54 trials and 2129 resource samples and 39600 operation records
All 5400 requests restored exact artifacts
The separate storage smoke audit checked 140 requests and 28 policy selections
The earlier large storage studies are retained in results/archive/preliminary and results/archive/iteration2
The 8 October changes add complete target operation checks and protect existing result folders
Today's stronger audit passed on the original 5400 request run without changing its measurements
See docs/history/PROGRESS_OCT8.md and results/validation/2026-10-08 for the earlier validation
The 9 October public-data audit covers 3600 requests and 720 selections across 24 histories
Planner V3 restored all 535 admitted requests and its 900 trial ablation preserved every V2 decision
The current research record is in docs/reserach_progress.txt and the latest test log is in results/validation/2026-10-09

## Review commands

Install the pinned Python 3.12 package with python -m pip install -e . and then run

```bash
bash run_benchmarks.sh
python -m recoverml.performance --audit-only --out results/milestone2/performance
python -m recoverml.audit results/milestone2/storage
python -m recoverml.audit results/milestone2/new_data_oct9
```

Each fresh run uses a new directory and records its own machine and environment and source hashes
Operation logs are raw JSONL compressed as operations.jsonl.gz and can be opened with Python gzip or gzip -dc
HASHES.json checks the performance input files and logs and plots
CHECKSUMS.json checks the submitted project files
Run source hashes match the code used for the experiment and operator hashes also guard restoration
The source implementation commit is f9c8d12fbdeb84c629b52a70477c382a5df97c6b

## Git history requirement

The excellent implementation level also asks for continuous development across Weeks 4–7
Today's commits and earlier published commits show their real dates
These technical changes cannot create evidence of development in earlier weeks
Keep making meaningful changes during the remaining course weeks and include validation with each change
Existing local files or genuine earlier work can be explained separately using their original evidence
The course calendar was not supplied so the instructor must confirm the week mapping

## Hardware and explanation

No special hardware or GPU is required for this prototype
A Linux CPU computer or VM provides the CPU and memory readings used here
The machine model and CPU quota are recorded in provenance.json
CPU utilization is explicitly an example in the supplied rubric so perf hardware counters are optional for this reading of the rubric

Before submission run the command on the submission machine and explain the graph and planner and exact restore checks in a short demonstration
The repository tests and traces help review the code and the student should understand the implementation and follow the course policy for AI assistance

## Useful next commits

1. Repeat the same experiment on the submission machine and compare the results
2. Repeat Planner V3 on another machine and compare the paired timings
3. Add larger public-data graphs and more non replayable boundaries
4. Profile the environment check and file reads before changing concurrency code

Use real work and real dates and keep the raw measurements even when a baseline is faster
