# Replayability frontier scaling study

This study tests Planner V2 and V3 and V4 on the public Iris dataset
It grows the replayable ancestry before an opaque step from 0 to 128 operations

The run contains 15 captured histories and 1350 timed planner executions and 120 exact restores
All 450 paired planner sets reached proven optima and returned the same objective
At depth 128 V4 used 69 variables while V2 used 1256 variables
The median history level speedup was 3.38 times and V4 was faster in 14 of 15 histories

`raw_planner_trials.csv` contains every timing sample
`restore_verification.csv` and `execution_traces.jsonl` contain the exact restore checks
`capture_manifests.jsonl.gz` contains every captured graph manifest
`summary.json` contains the statistical summary
The two PNG files show planning time and model size as frontier depth grows
