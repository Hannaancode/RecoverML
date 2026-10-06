# Milestone 2 rubric audit — 6 October 2026

This checklist uses the four supplied rubric screenshots and the current
RecoverML implementation. It records evidence and remaining work rather than
claiming a grade.

| Rubric | Weight | Current evidence | Remaining work |
|---|---:|---|---|
| Implementation and authenticity | 35% | Modular Python prototype with real capture, selection and restoration code and 22 recorded correctness tests | Genuine progress commits through the remaining project period and a code explanation or demonstration |
| Benchmark harness | 25% | Makefile, configurable automated benchmark, CI smoke workflow and experiments at 2,000 and 10,000 synthetic rows | Verify a fresh one-command run on the submission machine and retain its output |
| Trace data authenticity | 25% | Per-request CSV, operation JSONL, environment records, hashes and audit | New measurements with UTC start/end times, monotonic durations, CPU and memory samples, request counters and measured throughput |
| Preliminary plots and analysis | 15% | Prototype and baseline plots for recovery, storage and planning cost | Render latency CDFs, run concurrency-throughput trials and explain measured tail spikes and performance dips |

## Work completed today

Added scripts/tail_latency.py to calculate P50, P90 and P99 and export empirical
CDF points from recorded restore_s measurements. It groups by workload, policy
and storage budget. Exact successful requests contribute latency samples while
all requests remain visible in coverage counts.

Run from the repository root:

```bash
python scripts/tail_latency.py results/iteration2 --out results/tail_iteration2
```

Outputs:
- latency_percentiles.csv
- latency_cdf.csv
- provenance.json with the input SHA-256 and measurement scope

Validation on the existing iteration2 data:
- 11,200 requests accounted for
- 448 workload/policy/budget summary groups
- 6,223 distinct empirical CDF points
- Empty and singleton percentile cases checked
- Linear interpolation checked
- P50 <= P90 <= P99 <= maximum checked
- All nonempty CDFs reach 1 and are nondecreasing

This is analysis of the original measurements. It does not add missing historical
timestamps or CPU traces and is not a fresh performance run. Small groups have
limited tail estimates so future runs should collect more repeated samples.

## Next genuine commits

1. Instrument request start/end UTC and monotonic times and resource sampling
2. Run the instrumented benchmark and publish raw logs with run identity
3. Add CDF plots and a concurrency sweep with fixed workload and budget
4. Write anomaly analysis linked to the corresponding raw request records
5. Run the full reproduction command and record the final verification

Use real dated changes and their validation evidence. Do not backdate commits or
split unchanged content into artificial activity. The history published on
3 October does not establish continuous development in earlier weeks.

## Hardware

The rubric does not require buying equipment or using a GPU. A CPU computer
or VM can run this software project and collect CPU and memory measurements.
Record the machine details and available CPU limits so performance claims have
a clear context. Linux perf is one possible resource source; CPU utilization
is also listed as an example by the rubric.

## Result interpretation

Existing timing uses successful restore durations and warm-cache measurements.
Compare policies within the same workload and budget and report coverage
alongside latency. A throughput plot must use completed requests divided by
actual elapsed wall time; inverse per-request latency is not a measured
concurrent throughput result. New instrumentation cannot recover measurements
that were not recorded in earlier runs.

The benchmark rubric allows variation in thread counts, data scales OR batch
sizes. Existing data scales address that part. The excellent plots example
also names throughput versus concurrency, so a controlled concurrency study
is the clearest way to match that evidence.
