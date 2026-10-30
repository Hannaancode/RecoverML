# Milestone 4 evidence against the supplied rubric

This is a provisional self-assessment, not an instructor grade. The supplied rubric gives 3.75 points for architecture, 4.5 for empirical rigor, 3.75 for reproducibility, and 3 for writing, totaling 15. The four category descriptions are applied to the current 12-page ACM manuscript and committed artifact.

| Category | Evidence now available | Conservative band |
| --- | --- | --- |
| Architecture and novelty (3.75) | The paper states the exact recovery contract and systems contribution. `docs/ARCHITECTURE_CRASH_CONCURRENCY.md` diagrams publication, isolated readers and process-crash invariants, mapped to tests. | Excellent, subject to instructor review of novelty and diagram completeness. |
| Empirical rigor (4.5) | Version-length sweeps, same-host thread/process contention, 1/2/4 independent-runner aggregate capacity, per-trial P99 points, and a controlled 3-arm same-store ablation with 3,456 audited requests. Comparators and denominators are stated separately. | Excellent, subject to instructor judgment of workload breadth. |
| Reproducibility (3.75) | `scripts/rebuild_revised_paper.py` performs source gates, regenerates seven vector figures and compiles a 12-page PDF. A clean GitHub Actions rebuild and the same-store run preserve logs and hashes. Figure 6 now calculates from physical blob-size and selection ledgers. The original Letter frontier archive is still missing; four reconstructed payloads match archived identities. | Satisfactory conservatively; Excellent depends on whether the instructor accepts the ledger and reconstructed payloads as sufficient raw inputs. |
| Writing and formatting (3) | Twelve-page ACM two-column source and PDF, vector charts, concise captions, scoped comparisons and citations to related systems. | Excellent provisionally. |

If the first, second and fourth categories receive Excellent and reproducibility receives Satisfactory (2.81/3.75), the discrete-band total is **14.06/15 = 93.73%**. If the instructor accepts reproducibility as Excellent, the same evidence could receive **15/15**. The missing original archive prevents claiming 95%+ with certainty under the conservative interpretation. The new internal ablation strengthens empirical rigor but does not change the equal-storage ties with the manual frontier or prove superiority over every external comparator.

Milestone 2 is audited separately in `docs/MILESTONE2_HISTORY_EVIDENCE.md`. The original commit history is visible on `main`, but the course calendar needed to map it to Weeks 4–7 is not in the repository; its conservative scenario is **91.3%** and a 95%+ score remains unverified.
