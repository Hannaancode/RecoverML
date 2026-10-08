# Milestone 2 submission checklist

The package contains the working Python prototype, automated benchmark and
analysis commands, raw CSV/JSONL records, audited retention plans,
plots and experiment reports and CPU and memory measurements.
The public instructor-accessible repository is https://github.com/Hannaancode/RecoverML
Read docs/RUBRIC_AUDIT.md for the four rubric categories and the Git history requirement.

## Instructor review

Start with `README.md` and `docs/reports/ITERATION2_REPORT.md`. Install with Python 3.12
and `python -m pip install -e .`, then run `make test` and `make smoke`.
For the full new one-command rubric experiment run `bash run_benchmarks.sh` on Linux.
The supplied fresh results are in `results/milestone2` and their analysis is in `docs/reports/PERFORMANCE_REPORT.md`.
Run `python -m recoverml.audit results/runs/new_smoke` to check the smoke logs.
For the full repeated experiment, use `make iteration2`; it can take several
minutes on a single CPU thread and writes a new result directory.

Published raw measurements are in `results/archive/preliminary` and
`results/archive/iteration2`. The original experiment is preserved rather than
overwritten by the second iteration. Full experimental capture archives are
excluded from the compact submission; a complete small example is supplied,
and the harness can generate fresh complete histories locally.

## GitHub publication

1. Create or select the intended repository and copy these package contents
   into its root. The supplied `.gitignore` excludes full capture archives,
   generated policy stores, development runs and Python environments.
2. Commit the source, configurations, reports, raw measurements, plots and
   GitHub Actions workflow. Use your own Git author identity.
3. Push the commit. For a private repository, grant the instructor access;
   otherwise verify that the repository is readable without signing in.
4. Confirm the correctness/smoke workflow passes and the main README renders.
5. Submit the repository URL together with the commit SHA for this milestone.

Do not claim novel checkpoint optimization or superiority over published
systems from these measurements. The report distinguishes the improvement
over our original planner from comparisons with strong simple baselines.
