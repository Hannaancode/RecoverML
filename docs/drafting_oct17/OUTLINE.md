# Drafting outline and figure plan

Working title: **RecoverML: Auditable Retention for Exact Historical ML Recovery
under Declared Capability Loss**. The title is provisional. This is a plan for
the next writing session, not a replacement manuscript.

## Paper questions

1. What precisely must survive when some recorded producers cannot run?
2. Can retention choices be selected and checked efficiently for supported
   workflows, and when do simpler choices suffice?
3. How do failure grouping and capture boundaries change storage, recovery and
   planning costs compared with exact engines, robust heuristics and scoped
   published-policy adapters?

The core example should use a small historical image workflow: raw images
produce features and then a model and predictions. A corrected extractor
creates another version. If the old extractor is retired, retaining only the
raw images is insufficient for the old result; retained old features can
preserve the downstream replay path when training remains available. If
training is also unavailable, retaining the old models or outputs becomes
necessary. Explain the actual target and failure contract before suggesting
that any file can be deleted.

## Section order and provisional space

The 10–12 page allocation below is a planning aid, subject to the actual course
or venue instructions. It is not a claim that the current draft meets a final
format. Keep detailed receipts and extra grids in the artifact/appendix if the
rules allow it.

| Section | Approximate pages | Content and evidence |
|---|---:|---|
| Abstract | 0.25 | Write last; problem, precise service, scoped strongest result and tradeoff |
| 1 Introduction | 1.0 | Historical result problem, concrete example, three scoped contributions |
| 2 Related work | 1.0 | Materialization and reuse, historical recovery, robust selection, flow/abduction attribution |
| 3 Contract and architecture | 1.5 | Targets, physical identities, dependencies, loss groups, accounting, runtime assumptions |
| 4 Retention and verification | 1.75 | General exact routes, decomposition, guarded DAG specialization and proof checks |
| 5 Experimental method | 1.25 | Protocols, datasets, comparators, budgets, repeats, hosts, source cutoffs and unique-request counting |
| 6 Results | 2.0 | Shared-loss storage gap, capture controls, planning time, application/representation boundaries |
| 7 Discussion and validity | 0.75 | Manual ties, exploratory design, annotations, supported runtime and missing evidence boundary |
| 8 Conclusion | 0.25 | Answer the questions within measured scope |
| References | 1.0 | Verify bibliographic details and final numbering after prose is stable |

Approximate total 10.75 pages before adjusting the exact style and any appendix.

## Methods details to carry into the draft

Define grounded AND/OR recovery rather than only drawing a graph. Distinguish
logical artifact identities from physical blobs and count mandatory roots and
metadata once. State how alternative producers and declared loss groups work.
Give the complete-feasibility objective before discussing storage minimization;
partial coverage at smaller budgets is a different objective.

Describe the general exact implementations without claiming new implicit
hitting-set machinery. State the DAG specialization's eligibility guard,
integer network construction, selected payload cut and flow conservation/
capacity checks. Explain how equal lower and upper bounds establish optimality
for this model. Unsupported shapes must use the fallback. Preserve the
distinction between feasible, certified and storage-optimal statuses.

Describe both the planner and the recovery executor. Source checks and target
hash checks are part of the supported contract; they do not solve arbitrary
future environment drift. Do not imply distributed transactions, exactly-once
side effects or crash-consistent recovery, which were not implemented here.

## Results sequence

1. Show the new full shared-versus-separate grid and both capture boundaries.
   Lead with the specific 9/36 strong-local storage wins rather than the older
   universal-tie story. Preserve 27 ties, the manual optimum ties and the small
   size of the largest absolute gap. Explain the disclosed exploratory pilot.
2. Give published-adapter coverage at the stated common minimum budget and
   identify adapter code and original objectives. Robust full-budget storage
   comparisons are a separate table. Do not combine these into an overall rank.
3. Show paired planning ratios and absolute times. Separate cloud metadata
   planning, earlier scientific timing, and model recovery. Give all 48 earlier
   cases including the four slower runs.
4. Explain the EyeAI-inspired historical change and measured recovery. Follow
   with Letter's uncompressed/gzip/broader-loss controls and recovery cost.
   These establish scale of payload benefit and contract boundaries, not
   hardness of retention choices.
5. Add native DVC batch v2 only after its full protocol and checks close. Report
   the integration's wall time, core time, errors, and every slower case. Its
   common optimal frontier means latency, not lower storage, is the question.

## Figures and tables to prepare after the user reviews the paper

| Item | Intended message | Existing source or required input |
|---|---|---|
| Figure 1: small workflow and loss example | Why keeping raw data alone may not preserve history | Contract and real example above; create an original vector figure later |
| Figure 2: shared/separate loss × fused/concat storage | Fault grouping and capture granularity determine local-search gap | [72 complete cases](cloud_storage_cases.csv); aggregate all seeds rather than show one favorable seed |
| Figure 3: paired planning ratios and absolute times | Specialization helps supported shapes; fallback can be slower | [48 timing cases](planner_timing_cases.csv) and cloud cases |
| Table 1: comparator objectives and budgets | Make the comparisons interpretable | [Results tables](RESULTS_TABLES.md), per-seed protocols |
| Table 2: unique execution ledger | Recovery success and expected blocking have different meanings | [Combined summary](results_summary.json) and raw cloud audit |
| Table 3: retinal and large-payload controls | Application motivation and storage/recovery tradeoffs | Retinal analysis and Letter scopes |
| Optional Figure 4: native DVC v2 paired timing | Compare the two authored integrations fairly | Pending complete v2 dataset; no placeholder winner |

Existing per-seed [shared-loss figure](../../results/research/strong_baseline_cloud_oct16/seed20261016/shared/strong_baseline_comparison.png)
and scientific [storage/recovery plot](../../results/research/scientific_complete_oct16/storage_recovery_tradeoff.png)
are useful checks. They are not substitutes for a final all-seed figure.
No publication figure was regenerated during preparation.

## Last checks before formatting

Check all equations against implementation and attribution. Remove obsolete
headlines and unused duplicated tables from the old draft after retaining its
history. Use decimal GB/MB or explicitly labelled GiB/MiB consistently. Attach
each claim to a source field in the manifest. Keep training accuracy separate
from byte-exact historical recovery. Report record-level correlation rather
than treating every request as an independent scientific sample.

Close or disclose open reference/evidence gaps and obtain genuine reviews.
Then verify page limits, template, citation style and artifact-link access.
Write the abstract and conclusion after the final verified tables are frozen.
