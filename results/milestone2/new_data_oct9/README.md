# Repeated public data study

This folder contains the reviewable evidence from the Digits and Wine experiment

The experiment uses logistic regression and random forests and deterministic and opaque boundaries and three seeds
It contains 24 captured histories and 720 selections and 3600 recovery requests
The audit covers 10030 trace events and confirms the complete request matrix

Start with `success_by_budget.png` and `opaque_workload.png` and `summary.csv`
Use `raw_requests.csv` and `execution_traces.jsonl` to check individual requests
Use `retention_plans.jsonl` to check every planner decision and recovery certificate

Planner version 3 restored all 535 requests that it admitted and there were no unexpected failures
Version 2 and version 3 made identical decisions in all 144 paired selections
