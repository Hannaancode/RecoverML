# Milestone 2 evidence and commit chronology

This audit separates repository evidence from the instructor's judgment. The
historical [rubric audit](https://github.com/Hannaancode/RecoverML/blob/5c08783/docs/RUBRIC_AUDIT.md)
records four category weights: implementation and authenticity 35%, benchmark
harness 25%, authentic traces 25%, and preliminary plots and analysis 15%.
Its note says the excellent implementation level also asks for sustained
development in course Weeks 4–7. The exact rubric screenshots supplied on 30 October confirm maxima of 3.5,
2.5, 2.5 and 1.5 points. The Satisfactory implementation band is 2.63 points.
The course calendar is still unavailable, so the date-to-week mapping is open.

## Genuine repository history visible from `main`

Commit `0f49828` merges the original research history into `main` without
changing the project tree. Its archived parent `5b41e14` has 67 commits, with
these author-date counts (Git records, not independent proof of work time):

| Date in 2026 | Oct 3 | Oct 6 | Oct 7 | Oct 8 | Oct 9 | Oct 10 | Oct 11 | Oct 13 | Oct 14 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Commits | 27 | 3 | 3 | 3 | 2 | 3 | 4 | 16 | 6 |

Examples of substantive dated changes include the concurrent restore harness
(`f9c8d12`, Oct 7), audit of 5,400 exact requests (`4255188`, Oct 7), planner
V3 and public-data harness (`638de6c`, Oct 9), replayability frontier V4
(`6d7daf8`, Oct 10), neural and wide topology experiments (`a276b44`, Oct 13),
and publication of raw execution logs (`127bbd6`, Oct 14). Subsequent work on
`main` continues on Oct 16, 18, 26, 27, 28 and 30, counted across all parents
of `main`.
These commits establish a visible development sequence from Oct 3–30, but
cannot establish which dates were Weeks 4–7 or whether the rubric requires an
earlier start. No commits are dated October 19–25; this gap must be assessed
against the actual course dates.

## Category evidence

| Category | Directly inspectable evidence | Remaining check |
|---|---|---|
| Implementation and authenticity (35%) | `src/recoverml/`, `tests/`, historical code commits, and `docs/ARCHITECTURE_CRASH_CONCURRENCY.md` | Instructor must assess authenticity and map actual course weeks to commit dates. |
| Benchmark harness (25%) | `run_benchmarks.sh`, `Makefile`, `results/milestone2/performance/config.json` and `provenance.json` | Rerun on submission machine if required. |
| Authentic traces (25%) | `results/milestone2/performance/{requests.csv,resources.csv,operations.jsonl.gz,audit.json,HASHES.json}`; its audit reports 5,400/5,400 exact requests, 54 trials, 2,129 resource samples and 39,600 operation records. `results/milestone2/storage/audit.json` reports 140 requests across 28 selections. | Verify hashes and selected runs on the grading environment. |
| Preliminary plots and analysis (15%) | 16 PNG plots under `results/milestone2/`, including throughput vs concurrency, latency CDF and storage/planning plots; companion README and summary files. | Submit the performance report with the preliminary report; the dated submission supplement now links it explicitly. |

Under a **conservative provisional band assignment** of Satisfactory for
implementation (because the course-week mapping is unverified) and Excellent
for the other three categories, the weighted rubric score is
`2.63 + 2.5 + 2.5 + 1.5 = 9.13/10 = 91.3%`. If the instructor verifies the calendar
requirement and judges implementation Excellent, the same category assignment
would be 100%. The evidence cannot justify a definitive 95%+ claim before that
check. The screenshots explicitly require automated variation in thread counts, data
scales, or batch sizes; varying batch sizes is not an additional requirement
when the thread and scale sweeps are present. See the [submission guide](MILESTONE_SUBMISSION_GUIDE.md)
for the exact evidence and a saved-data audit command.
