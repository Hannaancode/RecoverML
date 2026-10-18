# Manuscript claim ledger

Updated 13 October 2026

The current manuscript is paper/RecoverML_draft.md and the readable review copy is output/pdf/RecoverML_paper.pdf

| Claim | Direct evidence | Scope |
|---|---|---|
| Original large graph has 1038 nodes and 1068 edges and 10.47 median speedup | results/milestone2/topology_scaling_oct11/summary.json and raw_planner_trials.csv | Older controlled numerical topology study |
| 128 logical graphs and 2048 subsets and 1890 matched solver comparisons | results/milestone2/oracle_oct13/summary.json and oracle_comparisons.csv | Small graphs with physical aliases and independent verification recursion |
| 45 control histories and 1215 optimal solver runs and 135 exact restores | results/milestone2/boundary_controls_oct13/summary.json and planner_trials.csv and restore_verification.csv | Executable small arrays and zero modeled replay cost |
| 1.00 and 1.91 and 10.13 control speedups with whole-seed intervals | results/milestone2/paper_evidence_oct13/boundary_control_statistics.csv | One machine and five seed blocks across three widths |
| 432 PyTorch requests and 12 histories and 834 trace events | results/milestone2/pytorch_validated_oct13/audit.json and raw_requests.csv | Final finite-output run only |
| 48 of 48 admitted V4 requests exact and 24 budget-blocked | results/milestone2/pytorch_validated_oct13/findings.json | Budget coverage differs from conditional exactness |
| At 50 percent budget V4 18/24 and target snapshots 6/24 | results/milestone2/paper_evidence_oct13/pytorch_coverage.csv | All requests stay in denominator |
| 24 native checkpoint weights and predictions match | results/milestone2/pytorch_validated_checkpoints_oct13/checkpoint_verification.csv | .pt interoperability and weights-only inference rather than training resume |
| CNN median accuracy 95.56 percent and text median 45.25 percent | results/milestone2/paper_evidence_oct13/model_quality.csv | Small fitted workload quality and no classifier superiority claim |
| Final weights and 63600 probability values are finite and normalized | Final checkpoint audit plus results/validation/2026-10-13 | Numerical validity is checked separately from byte identity |
| V4 is included in final plots | src/recoverml/analysis.py and tests/test_analysis.py | Earlier raw data unchanged and final plots use repaired analysis |
| 49 tests pass | results/validation/2026-10-13/tests.txt | Optional CPU PyTorch installed during validation |

claims.json is generated from raw files and input_hashes.json links those inputs to their exact content
The original unclustered boundary confidence intervals are not used in the manuscript
The initial PyTorch diagnostic run with nonfinite text outputs is retained and excluded from final quality claims

The novelty comparison credits prior slicing and frontier and exact bytes and MILP mechanisms
The current presolve distinction is a candidate contribution and not an independently established first-of-its-kind result
The configured extra CI job has not yet been observed so second-machine reproduction is not claimed
