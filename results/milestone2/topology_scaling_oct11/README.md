# Wide topology scaling study

This study tests whether the exact frontier result continues to help on wide executable DAGs
Every history contains several parallel replayable branches followed by a captured non replayable output and three replayable steps

It includes 15 independent histories and 315 timed planner executions and 45 exact restores
The largest graph contains 1038 nodes and 1068 edges
All solver runs reached proven optima and every V2 V3 and V4 objective agreed

The median V2 to V4 planning speedup is 10.47 times and the median variable reduction is 98.21 percent
The largest formulation falls from 7218 variables in V2 to 33 in V4 which is a 99.54 percent reduction

The graph executes real supported numerical operators but its values are deliberately small
It measures optimization topology scaling and does not claim neural training speed

The raw timing rows are in raw_planner_trials.csv and exact restore checks are in restore_verification.csv and operation events are in execution_traces.jsonl
HASHES.json protects every supplied result file

