# Complete durable strongest-baseline cloud rerun

Source commit: `00bd37a8addd6cea919edf2189c3246811bb669e`.
Execution: [GitHub Actions run 38945172079](https://github.com/Hannaancode/RecoverML/actions/runs/38945172079).
All three fixed seed blocks completed successfully. These are fresh captures
and executions, not reconstructions of the lost local correlated-loss logs.
The earlier four-history checkpoint remains labelled partial evidence.

## Scope and independently checked totals

Thirty-six constructed histories cover Wine and Breast Cancer, three seeds,
4/16/64 historical models, and both fused-view and explicit combined-table
capture boundaries. Each capture is tested under separate preprocessing losses
and a correlated shared-entrypoint loss. The paired contracts reuse identical
captured physical bytes. There are 72 history/contract cases, 648 method rows,
1,944 timed planner calls and 216 checked integer flow proofs.

| Phase | Histories | Actual unique recovery requests | Exact | Expected blocked | Unexpected |
|---|---:|---:|---:|---:|---:|
| Separate entrypoints | 36 | 12,180 | 9,963 | 2,217 | 0 |
| Shared entrypoint | 36 | 7,472 | 6,147 | 1,325 | 0 |
| Total | 72 paired contract cases | 19,652 | 16,110 | 3,542 | 0 |

Every request for RecoverML and each full-contract retention baseline succeeds.
Expected blocks belong to published reuse-materializer adapters under the
common minimum-byte budget. Identical stores share one explicitly attributed
execution ledger; they are not double-counted as additional actual requests.

## Comparison with strong local search

| Phase | Storage wins | Ties | Losses | Maximum reduction | Median paired planning speedup |
|---|---:|---:|---:|---:|---:|
| Separate | 6 | 30 | 0 | 0.1942% | 11.92 times |
| Shared | 9 | 27 | 0 | 48.7380% | 16.88 times |

The shared-loss wins occur in the fused Wine 16/64-version and Breast Cancer
64-version histories across all three seeds. All 18 explicit combined-table
controls tie local search. The median storage reduction over the complete
36-case shared grid is zero. The separate-loss differences are small
serialization overheads. This is a specific failure of the tested one-add
exchange heuristic, not evidence against every stronger local-search method.

The two exact formulations agree on all 72 case minima. The median paired
planning speedup over the scenario formulation is 2.28 times for separate
losses and 1.73 for shared losses. These are descriptive timings on three
runner hosts, not independent population estimates or recovery speedups.

## Comparator boundaries

The manual best frontier ties all 72 exact minima. This is a retention-set
control, not a new native DVC execution. Its hand-written workflow knowledge
and smaller planning overhead must remain visible. A native DVC latency study
is separately specified in `docs/NATIVE_FRONTIER_PROTOCOL_OCT16.md`; no result
from that study is implied here.

At the same minimum-byte budget, the HELIX rule achieves full recovery in
15/36 histories per phase, HYPPO rank in 18/36 and HYPPO frequency in 21/36.
RecoverML achieves 36/36. These adapters plan faster but optimize reuse-oriented
criteria. HYPPO uses its pinned released component and HELIX a documented rule
adapter; these results do not establish full native-system dominance.

Target snapshots and the robust heuristics remain feasible controls. Snapshots
trade larger retained stores for simpler planning and potentially faster loads.
Application priorities, not a post-hoc weighted score, determine which tradeoff
matters. The project contribution remains a checked system using established
optimization methods.

## Older conditions and provenance

The separate metadata-only timing study reruns all 48 original scientific
conditions, five repetitions and three methods: 720 calls. All exact bytes
match the frozen original minima. RecoverML is faster than local search in
44/48 conditions, with median paired speedup 4.20 times; the four slower cases
are retained. All 36 DAG-eligible cases are faster, median 6.27 times. The 12
general fallback cases have median speedup 1.64 versus local and 0.928 versus
the scenario solver. This is planner timing, not a new payload recovery study.

`complete_audit.json` independently reconciles the whole grid, source snapshots,
original ZIP member hashes, method attribution, raw requests, all flow proofs,
captured bytes, paired capture identity and the old-condition timing cross-links.
Duplicate, missing and replacement-duplicate requests are rejected. The runner
full suite passed 131 tests with six optional skips. The additional aggregate
auditor's targeted rejection tests pass. A Windows full-suite attempt records
five Linux/Bash/resource-tracing errors and is not labelled a full-suite pass.

Each seed's `artifact_receipt.json` records the original GitHub ZIP digest and
every member hash. Original top-level files are preserved byte-for-byte. The
original `captures.tar.gz` contains every omitted duplicate capture file;
all were checked. Original per-case JSON bytes are stored in the explicitly
new `case_receipts.tar.gz` transport archive. No model was loaded by the audit.
Raw evidence uses `-text` Git attributes to preserve original newline bytes.

Recheck after cloning with the pinned Python dependencies and `PYTHONPATH=src`:

```bash
python scripts/audit_cloud_followup.py results/research/strong_baseline_cloud_oct16 \
  --source-commit 00bd37a8addd6cea919edf2189c3246811bb669e --output work/new_cloud_audit.json
```

This completes the fixed durable correlated-loss rerun and its publication
checks. Genuine human review, global originality confirmation, the one missing
historical Letter archive container, and manuscript integration are separate
open tasks. This study does not recreate that original missing container.
