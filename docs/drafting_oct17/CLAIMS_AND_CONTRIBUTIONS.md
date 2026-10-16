# Three contributions and the claims they support

Position: **auditable retention planning for exact historical ML recovery under
declared processing-capability loss**. This is a candidate systems and empirical
contribution built with established optimization tools. The evidence cutoff is
`e0c745a754599e45562067197da76ea7de0dd0e5`.

## C1. Make the recovery promise precise

**Simple words:** We say which old results must survive and which processing
steps may stop working. We then check that the saved files are enough for every
allowed failure in that promise.

**Paper scope:** An explicit historical artifact-preservation contract combines
protected output identities, mandatory retained roots, declared correlated
producer-loss groups and common physical-byte accounting. A feasible retained
store must recover every protected target under every allowed loss.

This is useful because a normal reuse budget does not itself specify this
obligation. The contribution is the application contract and its implementation,
not the first use of provenance, robustness, reachability or exact restoration.
The guarantee assumes complete recorded dependencies, intact retained bytes
and the supported source/runtime semantics. It does not promise arbitrary
future library compatibility or recovery from every possible failure.

Evidence: [positioning review](../CONTRIBUTION_POSITIONING_OCT16.md),
[capability retention implementation](../../src/recoverml/capability_retention.py),
[new declared protocols](../../results/research/strong_baseline_cloud_oct16/seed20261016/shared/protocol.json).

## C2. Turn the promise into checked retention choices

**Simple words:** The program chooses which files to keep and gives a checkable
reason for the choice. It uses a faster exact route when the recorded workflow
has the required shape and a general route for other supported cases.

**Paper scope:** A checked executable service combines exact formulations,
grounded recovery and component decomposition with a guarded minimum-cut
specialization. In the supported single-producer physical DAG subclass, an
integer feasible flow and matching retained cut give a separately checked
optimality certificate. Recovered outputs are checked against their hashes.

The 72 new paired cases have matching exact minima and 216 checked flow proofs.
On the earlier 48-case planning grid the automatic path is faster than local
search in 44 and slower in four. The specialization applies in 36 cases and
is faster in all 36 of that subset. Median planning ratios belong to those
specific populations and do not describe restoration latency.

Credit established max-flow/min-cut, vertex splitting, logical closure,
implicit hitting sets and standard integer optimization. Do not present a new
general optimizer or new graph theorem. A heuristic feasibility check is not
an optimality proof. The two in-repository exact implementations are separately
coded checks and are not independent external implementations.

Evidence: [DAG implementation and proof checker](../../src/recoverml/dag_retention.py),
[component implementation](../../src/recoverml/component_retention.py),
[tractable subclass memo](../TRACTABLE_SUBCLASS_OCT15.md),
[cloud audit](../../results/research/strong_baseline_cloud_oct16/complete_audit.json),
[complete planning table](planner_timing_cases.csv).

## C3. Show when selective retention helps and why simple methods can tie

**Simple words:** We measure saved space and recovery cost in several real-data
workflows. We also show that the processing failures and the files recorded
between stages can change which saving is possible.

**Paper scope:** A reproducible empirical study measures contract sensitivity,
capture-granularity effects, exact recovery, strong-baseline differences and
ties, representation effects and recovery costs. The new exploratory
shared-loss grid improves on strong local search in 9/36 paired cases, ties
27/36 and reaches a maximum 48.7380% byte reduction. All 18 explicit-concat
controls tie, and the hand-picked optimal frontier ties every optimum.

The EyeAI-inspired STARE study grounds the historical-processing-change use
case and supplies exact recovery, but local search ties all 108 storage
comparisons. Letter demonstrates a 3.6647 decimal GB uncompressed saving under
preprocessing loss, with 48/48 actual exact recoveries, while gzip reduces that
saving to 290.61 MB and broader loss removes it. Strong heuristics tie the
Letter storage result and snapshots restore faster in its descriptive trial.

This is evidence about constructed histories from public data. It does not
estimate production prevalence or establish causal model-accuracy improvement.
The shared-loss grid followed a disclosed favorable pilot and is exploratory.
Three seed blocks do not create independent application populations. A native
DVC v2 latency advantage is pending, not part of this contribution yet.

Evidence: [all results and sources](RESULTS_TABLES.md),
[retinal results](../../results/research/eyeai_complete_oct15/analysis.json),
[large-payload results](../../results/research/gigabyte_letter_oct16/analysis.json).

## Wording checks before the abstract

| Proposed claim | Decision |
|---|---|
| Exact retained stores and checked recovery under the declared model | Supported with assumptions and proof status |
| A material local-search storage gap under shared loss | Supported on 9 of 36 exploratory constructed cases; give 27 ties and capture controls |
| Planning is faster on the supported DAG cases | Supported on the measured subset; report fallback and slower cases too |
| Automatically selecting and certifying a frontier | Supported functionality; manual optimal selection still matches storage |
| First robust optimizer or first exact restoration system | Not established by the review |
| Better than every published system | Not supported; adapter scope, objective differences, manual ties and pending native comparison matter |
| Three independent new mathematical inventions | Not supported; these are contract, checked-system and empirical contributions |
| One GB saved with compression | Not supported by the measured gzip representation |
| All experimental requests recovered | Incorrect; distinguish exact, expected blocked and unexpected |
| Complete original evidence archive or completed human reviews | Not established; keep their separate open status |

An acceptable paper can explain a useful boundary and a checkable system. Its
framing should follow the evidence rather than require a universal winner.
