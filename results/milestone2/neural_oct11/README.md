# CPU neural network study

This experiment uses the public handwritten Digits dataset and a deterministic scikit learn multilayer perceptron with one hidden layer
It captures three historical parameter versions under deterministic execution and under a genuine entropy backed random augmentation boundary

The matrix contains six histories and seven policies and five storage budgets and three protected versions
It records 630 requests and 210 policy selections and 1233 trace events
The audit found a complete request matrix and matching trace counts and no unexpected failures

Planner V4 admitted 63 requests and restored all 63 exactly and blocked 27 requests before execution when their budgets were insufficient
At the 50 percent budget V4 restored all 18 requested versions while full snapshots restored zero because they exceeded the budget and full replay restored nine because it cannot cross the random augmentation boundary
At feasible budgets V4 retained a median 27.28 percent of full captured bytes

This experiment establishes compatibility with a real CPU neural estimator and a real nondeterministic operation
It does not represent a large GPU model and target snapshots remain a strong baseline on this compact graph

The main files are raw_requests.csv and execution_traces.jsonl and retention_plans.jsonl and capture_metrics.csv and audit.json and findings.json
The plots summarize success by budget and planning overhead and behavior at the opaque boundary

