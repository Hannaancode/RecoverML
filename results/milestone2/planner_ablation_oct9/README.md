# Planner V3 ablation

This folder compares Planner V2 with the boundary aware Planner V3

The study repeats 30 opaque solver selections 30 times and records 900 paired timing trials
Every pair has the same selection status and the same retained artifacts
Version 3 reduces the model from 129 variables to 98 and the median history speedup is 1.18 times

Start with `planner_v3_ablation.png` and `summary.json`
Use `raw_planner_trials.csv` for every measured trial
Use `selection_medians.csv` and `history_medians.csv` for the two aggregation levels
