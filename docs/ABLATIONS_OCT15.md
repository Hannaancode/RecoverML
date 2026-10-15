# Component controls on 15 October 2026

These are fresh measured executions after reconstruction of lost auxiliary files. They do not validate earlier claims about absent results. The protocol was committed before measurement at local commit db9a4da and its exact content and source hashes are saved with the run.

## Scope and evidence

The [protocol](../configs/component_ablations_oct15.json) declares four public-recipe captures at seed 101 with broad loss bounds 1 and 2 and three small constructed fixtures. Seven controls run twice on each of these 11 cases. This produces 154 planner rows and 110 preserve exactly the same recovery contract. The source is [audit_component_ablations.py](../scripts/audit_component_ablations.py) and the evidence is in [component_ablations_oct15](../results/research/component_ablations_oct15/report.json).

The audit loads immutable capture manifests and never loads their model or array payloads. It runs actual optimization and grounded structural certificates. It does not measure fresh historical disk recovery or model execution.

| Control | Same recovery contract | What it checks |
|---|---|---|
| Default | Yes | Current root-conditioned components and automatic exact-engine choice |
| No decomposition | Yes | Automatic exact engine on the full graph |
| No root shortcut | Yes | Solve atomic components using the exact engine instead of the direct root-provider rule |
| Forced scenario without decomposition | Yes | Independent scenario-expanded exact formulation on the full graph |
| Forced counterexample without decomposition | Yes | Counterexample-guided exact formulation on the full graph |
| No alternative producers | No | Keep the first replayable producer of each output and mark later producers unavailable |
| Logical identity | No | Charge every logical captured node as its own selectable output identity |

Changed-contract controls retain all provenance nodes and are reported separately. In particular their metadata bytes can differ. Their payload-only differences help describe the mechanism but are not evidence of a speedup for the same optimization problem. The logical-identity labels are synthetic structural labels rather than new content hashes or executed artifacts.

## Results

All 154 controls completed with certified optima and zero unexpected errors. All 110 same-contract rows agree on their case's optimal retained bytes. That provides 99 comparisons against one certified case reference and 1452 enumerated fault/certificate checks across the full seven-control matrix. No unknown or timed-out row was removed.

A separate [reconciliation](../results/research/component_ablations_oct15/analysis.json) recomputes every one of those 1452 closures using an independent full fixed-point scan and compares it with the indexed certificate. All available artifact sets and version-coverage results agree. These are fresh post-run structural checks and are not reconstructed timings or historical disk-recovery measurements.

The following table compares retained payload bytes with the default and reports each real history only once per loss bound. It excludes changing manifest costs from the changed-contract comparison.

| Real captured recipe | Loss bound | Extra payload after removing additional producers | Extra payload with logical identity |
|---|---:|---:|---:|
| Iris feature union | 1 | 0 bytes | 431 bytes |
| Iris feature union | 2 | 0 bytes | 431 bytes |
| Digits PCA | 1 | 0 bytes | 0 bytes |
| Digits PCA | 2 | 0 bytes | 0 bytes |
| Diabetes polynomial features | 1 | 0 bytes | 0 bytes |
| Diabetes polynomial features | 2 | 0 bytes | 0 bytes |
| Digits random forest | 1 | 0 bytes | 0 bytes |
| Digits random forest | 2 | 0 bytes | 0 bytes |

This is an important negative result. The real public-recipe histories do not establish a practical storage benefit from having multiple producers for the same exact output. The constructed alternative-producer fixture saves 418 payload bytes through surviving alternatives and proves that the mechanism can work. It does not establish its natural frequency in scientific workflows.

Full-archive output accounting is reported separately in [archive_output_accounting.json](../results/research/component_ablations_oct15/archive_output_accounting.json). Summing captured logical outputs rather than unique physical outputs adds 431 bytes for Iris and zero bytes for the other three real captures. This is a comparison of complete captured output sets and is not a no-deduplication retention optimizer. It also does not charge repeated references to one already merged logical node as additional full copies.

## Planner cost and root shortcuts

The default is slower than the undecomposed automatic engine in six of the eight real-recipe settings and faster in two. These small graphs therefore do not establish an unconditional benefit from decomposition. The three constructed fixtures have atomic optional components and the direct root-provider rule avoids their solver calls. That establishes the expected effect on those fixtures.

Only two repetitions were run and other experiments shared the host. Timings include Python and solver initialization and order effects. They are descriptive implementation measurements and do not support statistical speedup claims.

The indexed certificate and an independent full fixed-point scan agreed in all six chain controls. Both perform actual grounded closure on exactly the same graph and retained roots.

| Chain length | Repetitions | Median indexed closure | Median full-scan closure |
|---|---:|---:|---:|
| 128 | 3 | 0.235 ms | 7.171 ms |
| 1024 | 3 | 1.929 ms | 482.760 ms |

The scan deliberately revisits all producers until no more facts appear and the indexed implementation updates the dependencies affected by newly available facts. This is the established reason for worklist indexing and it is not claimed as a new algorithm. The measurement is a closure control rather than end-to-end recovery throughput.

## Separate baseline annotation controls

The [sensitivity report](../results/research/scientific_sensitivity_oct15/RESULTS.md) uses the earlier frozen nonuniform-cost protocol and all eight captured histories. It completed 5760 structural conditions with zero budget or eligibility errors. There are 4320 pinned HYPPO-component rows and 1440 HELIX-rule rows.

| Changed setting | Paired comparisons | Selected-set changes | Exact structural request-count changes |
|---|---:|---:|---:|
| Nonuniform operation costs | 4608 | 298 | 139 |
| Declared access weights | 2880 | 312 | 232 |
| Eligible artifact types | 2880 | 2190 | 1727 |
| Read-speed assumption | 960 | 140 | 32 |
| HELIX tie order | 720 | 180 | 60 |

These are correlated controls on eight histories and do not represent 5760 independent workflows. The declared access weights are not measured real user behavior. Structural coverage is not a new runtime replay result. Both changed and unchanged decisions remain in the saved evidence.

## Reproduction

From the repository root with the pinned paper dependencies installed use the manifest-only input archive. These commands create new output paths and refuse to overwrite evidence.

```bash
mkdir -p work/component_audit_inputs
tar -xzf results/research/scientific_sensitivity_oct15_inputs.tar.gz -C work/component_audit_inputs
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/audit_baseline_sensitivity.py --captures results/research/scientific_sensitivity_oct15_inputs.tar.gz --output work/fresh_sensitivity --hyppo-cache /path/to/HYPPO/Components
PYTHONPATH=src python scripts/analyze_baseline_sensitivity.py work/fresh_sensitivity
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/audit_component_ablations.py --captures work/component_audit_inputs --output work/fresh_ablations
PYTHONPATH=src python scripts/analyze_component_ablations.py work/fresh_ablations --captures work/component_audit_inputs
PYTHONPATH=src python -m unittest discover -s tests -p test_component_ablations.py -v
```

The HYPPO source revision and file hash are verified by the existing source adapter. The original audit and its report are retained so new runs can be compared without replacing measured data.
