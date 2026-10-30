# Milestone submission evidence

The current rubric estimates are conditional assessments. Course dates and the instructor's assessment of the real commit history determine the Milestone 2 implementation band. No history has been backdated or fabricated.

## Milestone 2

Submit [the preliminary report](reports/PRELIMINARY_REPORT.md) together with [the performance report](reports/PERFORMANCE_REPORT.md), its linked throughput and latency CDF figures, and the repository URL. The performance report was originally committed on 7 October; later manuscript supplements are explicitly dated.

| Rubric category | Evidence to inspect |
| --- | --- |
| Implementation and authenticity, 3.5 | [Source](../src/recoverml), [tests](../tests), [genuine history audit](MILESTONE2_HISTORY_EVIDENCE.md). Weeks 4–7 coverage is unverified; there are no commits dated October 19–25. |
| Automated harness, 2.5 | [run_benchmarks.sh](../run_benchmarks.sh), [fixed grid](../configs/performance.json): 2 data scales, 3 worker counts, 3 policies, 3 repeats. Fresh resource measurements require Linux or WSL. |
| Trace authenticity, 2.5 | [Saved performance evidence](../results/milestone2/performance): 5,400 exact requests, raw timestamps, service/response P50/P90/P99, throughput, CPU/RSS samples, hardware and source provenance. |
| Plots and analysis, 1.5 | [Performance report](reports/PERFORMANCE_REPORT.md): two baselines, throughput error bars, latency CDFs, quantified concurrency dips, queueing tails and an identified latency outlier with an explicitly uncertain cause. |

After installing Python 3.12 and the pinned package dependencies, audit the saved evidence with:

    python scripts/audit_milestone2_release.py

This checks exact recorded bytes, trial/request identities, percentile and throughput arithmetic, resource samples and operation links in a temporary copy. The checkout preserves original evidence line endings on both Windows and Linux. A fresh run uses:

    bash run_benchmarks.sh results/runs/NEW_DIRECTORY

The runner refuses an existing output directory. A new audit is not a fresh experiment or an independent attestation of the old run.

## Milestone 4

Submit the [12-page paper](../output/pdf/RecoverML_paper_revised.pdf), [TeX source and figures](../paper/acm_revised), [artifact guide](ARTIFACT_GUIDE.md), [architecture/state diagrams](ARCHITECTURE_CRASH_CONCURRENCY.md), and [rubric evidence](MILESTONE4_GRADE_EVIDENCE_OCT30.md).

The artifact guide links same-host scaling, independent-runner capacity, P99 trial distributions and the controlled same-store ablation. The paper build checks the recorded inputs and regenerates seven vector figures:

    python scripts/rebuild_revised_paper.py --tectonic PATH_TO_TECTONIC

The [figure source audit](PAPER_FIGURE_SOURCE_AUDIT_OCT30.md) identifies lower-level measurements. The missing original Letter archive is disclosed; its replacement payloads match recorded hashes and sizes. Figure 6 can be reproduced from blob-size and selected-set ledgers, but the missing original container identity cannot be independently checked. The instructor determines whether this meets the Excellent reproducibility band.
