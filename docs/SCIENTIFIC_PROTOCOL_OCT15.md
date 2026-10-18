# Prospective scientific validation protocol

Frozen before evaluating the new workflows on 15 October 2026

The parameter grid is `configs/scientific_audit_oct15.json` and its Git commit and file hash will be recorded by the runner before capture
The new greedy and local search baselines solve the same bounded replay group loss problem and do not claim storage optimality
The existing independent scenario expanded MILP remains the exact reference

Budgets are mandatory inputs plus original manifest and capability contract plus a fixed fraction of unique target snapshot payload bytes
These five limits are chosen without looking at RecoverML's storage optimum
The exact minimum is evaluated once and is admitted at a budget only when it fits
Below that minimum the exact policy reports infeasible and uses the mandatory set for transparent request accounting rather than an over-budget store
The reference exact solver follows the same admission rule
Every baseline reports actual stored bytes and complete or partial recovery and every policy sees exactly the same requests
The target snapshot baseline stores whole versions in chronological order while they fit and is labelled as a budgeted snapshot baseline

Eight new captures cover four different public recipe adaptations and two fixed seeds and three model versions
The new recipes include real branching with PCA and feature selection and new polynomial regression on Diabetes and a larger forest control
No duplicate producer is inserted to force identical feature hashes
These are additional constructed histories inspired by public examples and not independent production traces
All classification and regression predictions are checked against native sklearn model output
Training data alone fits each preprocessing state and targets include the captured model and its test predictions

Two capability scopes are tested and both include the no-loss case
The preprocessing scope groups split membership and feature operations
The broad scope also permits training and prediction group losses
All combinations up to each declared loss bound are enumerated
The bounds and scopes share the same capture and are correlated conditions rather than independent samples

Recorded metrics include payload and metadata bytes and exact or blocked or unexpected request outcomes and monotonic wall time and CPU time and process peak memory and Linux process I/O counters
Peak memory is a process high-water mark and is not presented as isolated per-request memory
I/O counters reflect the OS page cache and do not measure device-level physical traffic exactly
No GPU or energy claim follows from CPU timing
Recovery trade-off plots include only complete recovery at the stated fault contract and incomplete points are shown separately
Repeated requests and multiple fault scenarios do not inflate the number of independent histories

The sensitivity pass changes cost annotations and tie orders and HELIX load rates over the fixed captures
This is a decision-rule sensitivity experiment and does not change the actual measured hardware speed or rerun native HELIX
Complete rows and negative results will remain in the output even when there are no savings
The source and protocol are hashed and earlier milestone evidence remains unchanged

Paper drafting and formatting are outside this execution request
Fresh-environment measurements and external scientific review are distinct validation activities
