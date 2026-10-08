# Fresh worker and latency experiment

RecoverML restored all 5400 measured requests with exact artifact hashes and the trace audit passed
The run tested three policies at two data sizes and three worker counts and repeated every setting three times
All 23 correctness tests passed before the benchmark started and the storage smoke audit also passed

## Method

Run bash run_benchmarks.sh to create tests and storage checks and performance results
The published run is results/milestone2 and started on 7 October 2026 at 03:00:29 UTC and finished at 03:01:15 UTC
Each history has five logistic regression versions on seeded synthetic data
The data sizes are 2000 and 10000 rows and worker counts are 1 and 2 and 4
Each trial submits a burst of 100 requests and cycles through the five versions
There are three repeats per setting and policy order is shuffled with a fixed seed
Each worker uses one BLAS thread and each request has its own restore state
Restoration reads a selected disk store and cannot access the capture archive
Capture and policy planning happen before the timed trial

The available byte budget is the full deduplicated capture size for all policies on the same history
The retained size can differ and is recorded in plans.json and summary.csv
This experiment measures admitted restore throughput and the older budget studies measure which requests can be admitted under smaller budgets

Every version is warmed before each trial so these are warm page cache results
Service latency includes environment validation and reading or rebuilding and artifact hash checks
Response latency also includes executor queue wait
Throughput is exact completed requests divided by actual submission-to-completion wall time
This is instrumented throughput and includes executor overhead and operation trace logging and gzip compression
Those costs can influence the worker comparison and the logs do not isolate their effect
CPU and RSS samples cover the whole benchmark process and include sampler overhead
CPU percent is relative to one core and may exceed 100 percent
RSS means resident memory and is sampled every 20 ms where scheduling permits
The reported peak is a sampled peak and short memory spikes can be missed
The machine is an Intel Xeon Platinum 8573C Linux environment with a cgroup quota of eight CPU cores
The environment and source hashes and measurement scope are in provenance.json

## Main results

This table shows mean throughput over three trials in exact restores per second

| Rows | Policy | 1 worker | 2 workers | 4 workers |
|---:|---|---:|---:|---:|
| 2000 | Full replay | 104.6 | 85.6 | 64.1 |
| 2000 | Direct target snapshots | 890.2 | 444.0 | 409.8 |
| 2000 | RecoverML v2 | 859.5 | 484.1 | 397.5 |
| 10000 | Full replay | 31.7 | 37.8 | 40.9 |
| 10000 | Direct target snapshots | 854.6 | 469.7 | 443.3 |
| 10000 | RecoverML v2 | 774.8 | 479.3 | 400.7 |

Version 2 is about 8.2 times faster than full replay at 2000 rows and about 24.4 times faster at 10000 rows with one worker
These ratios compare mean throughput in this run and are not a general speed guarantee
Direct target snapshots remain a strong baseline and are slightly faster in these one worker settings
Version 2 can use the same direct target shortcut so similar restore latency is expected
The difference includes measurement variation and does not prove a planner advantage

![Throughput against concurrency](../../results/milestone2/performance/throughput_vs_concurrency.png)

Error bars show one population standard deviation across three trials and are not confidence intervals

![Service latency CDF](../../results/milestone2/performance/latency_cdf.png)

The CDF pools 300 successful service times per policy and data size at one worker
The horizontal axis is logarithmic and each curve reaches one
P50 P90 and P99 for service and response times are in summary.csv for every trial
With 100 requests per trial P99 depends strongly on the slowest few samples

## Dips and tail analysis

The small restore workload loses throughput as more workers are added
At 2000 rows version 2 goes from 859.5 requests per second to 397.5 at four workers
Its median trial service P50 rises from 1.01 ms to 9.55 ms
The process CPU time divided by wall time is about 1.02 with one worker and 1.11 with four
This limited CPU scaling is consistent with Python work and shared environment checks and file operations adding contention
The logs do not isolate those causes so a profiler is the next step before choosing a fix
The CPU quota is eight cores and measured use is far below that quota so the results do not demonstrate quota saturation

Full replay behaves differently on the larger history
At 10000 rows its throughput rises from 31.7 to 40.9 as workers rise from one to four
CPU time divided by wall time rises from about 1.01 to 1.90
The larger rebuild has more computation that can overlap and measured CPU scaling is consistent with that explanation
Service P50 still rises from 30.27 ms to 93.23 ms as requests compete for resources

Response tails are much larger than service tails because all 100 requests are submitted as one burst
At 2000 rows and one worker the median trial version 2 service P99 is 1.97 ms and response P99 is 114.22 ms
The timestamps show queue wait directly and no dropped requests are excluded
This burst model is not a steady arrival rate experiment

One version 2 request creates a visible tail in the 10000 row CDF
Trial rows10000-recoverability_v2-w1-rep1 and request 18 has service time 34.675579 ms
It started at 2026-10-07T03:00:54.790692+00:00 and restored version 3 exactly
The next highest service time in the pooled group is 2.702046 ms
Find the request in requests.csv and its artifact operations in operations.jsonl.gz using trial and request_id
The request includes environment validation that has no separate operation span and sampling is every 20 ms
These traces cannot establish whether scheduling or validation caused the outlier
We retain the sample and report that uncertainty

## Evidence and next work

The audit checks request counts and timestamp order and queue plus service arithmetic and throughput and percentile recomputation and operation links and file hashes
It verified 5400 exact requests and 54 trials and 2129 resource samples and 39600 operation records
The operations contain measured action times and byte counts and exact hash checks
They join to request UTC and monotonic boundaries using trial and request_id
This audit checks internal consistency and hashes and does not independently prove every external claim about execution
The raw CSV and JSON and compressed JSONL and plots are included with the config and source hashes
Tests include concurrent restore isolation and detection of a corrupted operation log
Future work will profile validation and repeat this experiment on the submission machine and add opaque histories and larger data
Genuine progress commits should record those changes and their measured results
