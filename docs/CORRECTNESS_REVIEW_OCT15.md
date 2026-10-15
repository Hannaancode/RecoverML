# Correctness and robustness review on 15 October 2026

This is an adversarial code and evidence review performed within the project. It is not an external human review or a formal proof checked by a proof assistant. The manuscript and its formatting were not changed.

The bounded replay loss mathematics is consistent under its declared assumptions. A real executable-depth defect was found and fixed and defensive solver postconditions were strengthened. All 1,440 inspected policy stores agree with their recorded byte accounting. Independent formulations re-certified 192 of 194 archived graph cases under the present resource settings and two larger direct formulations timed out without proving an optimum. Those outcomes remain in the evidence.

## What was checked mathematically

The six propositions in `paper/RecoverML_capability_loss.md` were compared with `src/recoverml/capability_retention.py`, `scenario_retention.py`, `component_retention.py` and `witness.py`.

1. **Closed set equivalence:** each available producer requires its output whenever all distinct physical dependencies are present. The least grounded closure is contained in every such closed superset. Thus a closed superset containing the store but missing a target exists exactly when grounded recovery fails for that loss. Self aliases and larger physical cycles do not invalidate this reasoning.
2. **Necessary storage cuts:** under a breaking loss a store wholly contained in the returned closed set cannot recover its missing target. Any robust store must therefore intersect its complement. The code independently checks the disabling set and closure and grounded reachability before using this cut.
3. **Certified byte minimum:** necessary cuts make the master optimum a lower bound on every robust store. A universally certified store reaching that bound is optimal within the encoded integer model and solver tolerances. A timeout or an unproved incumbent cannot establish this conclusion.
4. **Indexed certificate equivalence:** the missing-dependency counters release each producer in the same round as the scanning implementation and the heap uses the same producer order. Physical alias suppression therefore selects the same witnesses. Existing tests compare entire certificates including round numbers and event ordering.
5. **Root conditioned decomposition:** every live optional output and each optional dependency share a physical component. After mandatory roots are fixed no executable dependency crosses components. Universal quantification over allowed losses commutes with conjunction over components. Each local loss of at most k groups is also an allowed global loss and each global loss restricts to such a local loss. Shared labels therefore do not couple the local retention choices under this specific universal contract.
6. **Rooted provider reduction:** a singleton optional target survives without retention if an ungrouped rooted producer exists or more than k distinct rooted groups exist. Otherwise one allowed loss disables every rooted producer. An alias needing the absent target cannot supply its own initial value.

These arguments depend on complete dependencies and correct purity and deterministic replay declarations and intact retained data and the stated environment contract. They do not prove absence of all implementation defects and they do not imply tolerance of arbitrary source loss or disk corruption. Numerical MILP certificates use floating point tolerances rather than arbitrary precision proof objects.

## Concrete defects and changes

### Grounded certificates did not imply executable depth support

A captured chain of 2,048 deterministic affine operations produced a complete indexed certificate but the old recursive `WitnessRestorer` raised `RecursionError`. Shallower chains of 50 and 600 operations restored their exact bytes in the same diagnostic. This is a real observed implementation failure.

`src/recoverml/witness.py` now executes a request's grounded witness with an explicit postorder stack. It preserves dependency order and memoization and target-only traversal and output hash checks. Inclusive event elapsed times retain their previous meaning. A retained file disappearing after certificate construction now raises `RestoreError` rather than leaking a filesystem exception. Corrupt retained files still fail closed and are not silently bypassed by another producer.

Evidence:

- `results/validation/2026-10-15/scientific_audit/deep_chain_before_fix.json`
- `tests/test_scientific_negative.py::ScientificNegativeTests.test_deep_grounded_chain_recovers_without_python_recursion`
- `tests/test_scientific_negative.py::ScientificNegativeTests.test_dependency_order_and_shared_subgraph_execute_once`

The existing depth benchmark measures certificate construction only. Its earlier results are unchanged and should not be described as earlier successful deep restoration runs.

### Defensive master validation was incomplete

A deliberately inconsistent mocked successful solver result could select a five byte artifact while reporting a zero variable objective. The previous capability master accepted the resulting inconsistent byte lower bound if the separate oracle certified the selected store. This was a defensive solver trust gap rather than an observed wrong answer from real HiGHS.

`src/recoverml/capability_retention.py` now checks finite and near-integral binary values and mandatory roots and every accumulated cut and byte budget and objective consistency before issuing an optimum. It records the solver gap and dual bound when available and records postcheck tolerances. A rejected incumbent never receives a robust or optimum flag.

Evidence:

- `results/validation/2026-10-15/scientific_audit/solver_postcondition_before_fix.json`
- `tests/test_scientific_negative.py::ScientificNegativeTests.test_inconsistent_master_objective_is_rejected`
- `tests/test_scientific_negative.py::ScientificNegativeTests.test_nonfinite_and_fractional_master_values_are_rejected`
- `tests/test_scientific_negative.py::ScientificNegativeTests.test_master_must_satisfy_previously_generated_storage_cuts`

## Archived optimum and storage audit

Run the reproducible metadata and byte audit with:

```bash
PYTHONPATH=src python scripts/audit_storage_optima.py \
  --output results/runs/storage_audit_new.json
```

The output path must be new. The script reads archives without extracting them or unpickling their payloads. It resolves archive hardlinks and counts each independent policy store using file lengths as in the original measurements. It validates payload filename hashes and actual payload and manifest and capability metadata totals and compares recorded CSV byte totals wherever available.

| Archived suite | Policy stores checked | Graph and bound cases |
| --- | ---: | ---: |
| protocol_pilot | 288 | 32 |
| tabular | 432 | 48 |
| estimators | 72 | 8 |
| published | 560 | 56 |
| merged | 4 | 2 |
| components | 12 | 12 |
| fault_scope | 72 | 36 |
| Total | 1,440 | 194 |

There were 1,424 direct CSV byte comparisons and zero accounting errors and zero certified optimum disagreements and zero structural failures in the selected safe policy stores. Every allowed loss set was independently checked structurally for those selected stores. The 194 cases include repeated histories across experiments and loss bounds and are not 194 independent statistical subjects.

The first run guarded direct formulations above 100,000 estimated variables. It independently re-certified 192 cases with both the decomposed and scenario-expanded formulations and recorded two guarded cases. The unchanged first report is `results/validation/2026-10-15/scientific_audit/storage_optima.json`.

A supplementary run raised that guard to 250,000 for the component suite and preserved its complete result in `storage_optima_components_expanded.json` in the same folder. The two previously guarded cases reached the requested 30 second internal solver limit without proving optimality:

| Case | Known archived and decomposed minimum | Expanded feasible incumbent | Expanded status |
| --- | ---: | ---: | --- |
| g40-w18-k2 | 66,464 bytes | 75,172 bytes | time limit and optimum unknown |
| g40-w28-k2 | 93,707 bytes | 102,415 bytes | time limit and optimum unknown |

Both expanded incumbents were structurally robust but larger than the certified minima. They are not independently certified optima. Actual solver wall times were about 32.55 and 37.66 seconds and complete calls took about 34.72 and 44.56 seconds because the internal time limit is not a hard process deadline. These were audit runs with other work on the host and their times are not controlled speedup measurements.

Earlier archived independent certificates and analytic arguments for these families remain available. Their existence does not change the fact that the new direct runs timed out. The byte audit covers the seven archived-store suites listed above. Other historical analytic scaling runs and course milestone latency objectives are not silently included in that scope.

## Negative tests and actual execution

`tests/test_scientific_negative.py` adds 17 tests covering:

- Master and oracle and expanded solver timeout outcomes with and without incumbents
- A valid timed-out counterexample providing a cut while leaving minimum failure cardinality unproved
- Inconsistent and nonfinite and fractional and cut-violating mocked master responses
- A two-blob alias cycle checked with all three exact engines
- Missing retained files and corruption and environment drift
- Undeclared nondeterminism detected by output byte hashes
- Deep grounded execution and shared-branch order and memoization

All 17 new tests passed. A complete suite run recorded 96 tests with 91 passes and five optional PyTorch tests skipped in that particular isolated environment. Its full output is `results/validation/2026-10-15/scientific_audit/correctness_full_tests.txt`. Optional PyTorch validation performed elsewhere must be reported separately and those five skips must not be relabeled as passes in this log.

Existing exhaustive tests are substantive rather than only snapshots of implementation output: closure is compared with a separately written path search and retained subsets and loss sets are enumerated. Existing oracle tests also verify that each returned cut intersects every truly robust retained set on small cases. They cover many generated cases but do not replace proofs or arbitrary-size validation.

## Task 7 to 14 assessment within this review

| Task | Status | Reason and boundary |
| --- | --- | --- |
| 7 Mathematical correctness | PASS within the formal contract | The six arguments were checked against code and existing exhaustive independent path search controls plus a new multi-blob cycle check found no mathematical counterexample. This is an internal review and not a formal proof assistant certificate or external theorem review |
| 8 Every reported storage optimum | PARTIAL | Seven archived-store suites and 194 cases were checked and 192 were freshly certified by both formulations. Two new direct runs remained unknown and other historical objectives and analytic-only suites have a separate scope |
| 9 More realistic failures | PARTIAL | Existing broad training and prediction call restrictions and new corruption and missing file and environment drift checks establish the stated boundaries. They do not establish recovery from real package removal or arbitrary missing source data |
| 10 Separate environment reproduction | BLOCKED for an independent machine | This review ran on the same underlying host. A new virtual environment is useful installation evidence but cannot count as another physical or cloud machine |
| 11 Storage and restoration cost | PARTIAL | Existing request logs include measured elapsed time and CPU time and process peak RSS. The study does not establish energy costs or deployment economics or complete storage versus latency Pareto coverage |
| 12 Larger models and graph diversity | PARTIAL | Working forests and neural inference artifacts and layered branching graphs exist and the new deep restoration regression closes one genuine scale failure. These are not evidence for large language model recovery or arbitrary large DAG support |
| 13 Full ablation suite | PARTIAL | Indexed certificate comparisons and component and engine controls exist. Each requested component has not yet been disabled separately with all correctness and storage and recovery costs reported |
| 14 Negative coverage | PARTIAL at this checkpoint | The new negative cases and full non-Torch suite pass. The log still has five optional Torch skips and it does not exhaust every malformed trusted-manifest or operating-system failure |

## Hardware and safety boundary

No GPU was needed for this review or either solver or the exact affine and forest and small neural workload scope. A separate laptop or cloud CPU machine can provide the missing independent-machine evidence if it performs a fresh clone and records its own environment and outputs. Cross-machine replay must respect the existing strict environment guard. Disabling that guard does not establish the promised cross-environment guarantee.

The system's byte and environment checks detect supported integrity failures. Its retention theorem assumes intact retained files and does not promise storage redundancy against losing those files. Trusted local manifests and trusted serialized artifacts are the current input boundary. A security claim about maliciously rewritten manifests or externally supplied pickle objects would require a separate threat model and implementation.

The remaining independent environment and broad ablation and operational realism questions should stay open in the final project audit. This review supports the restricted exact recovery contract and the observed experiments and does not justify a claim of 100 percent research confidence or guaranteed acceptance.
