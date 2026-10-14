### Verified comparison tables

| Policy | Tabular exact requests | Larger model exact requests |
|---|---:|---:|
| RecoverML | 3168/3168 | 176/176 |
| Expanded exact | 3168/3168 | 176/176 |
| Nominal exact | 1728/3168 | 64/176 |
| HYPPO rank | 2069/3168 | 168/176 |
| HYPPO frequency | 2145/3168 | 166/176 |

![Exact recovery at common robust budget](../results/research/paper_oct14/analysis/coverage_comparison.png)

| Dataset | Lossless k=1 saving | Lossless k=2 saving | Rounded k=1 saving | Rounded k=2 saving |
|---|---:|---:|---:|---:|
| breast cancer | 17.75% | 0.00% | 0.00% | 0.00% |
| iris | 44.34% | 34.34% | 34.34% | 34.34% |
| wine | 39.09% | 11.64% | 11.63% | 11.63% |
| banknote | 43.24% | 13.96% | 13.96% | 13.96% |

![Storage sensitivity to format and outage bound](../results/research/paper_oct14/analysis/storage_conditions.png)

### Larger trained artifacts

The corrected Digits experiment contains 4 histories and 8 planning cases and 1584 requests across nine policies and the robust and expanded exact methods each recover 176 of 176 requests. Forests use 24 to 48 trees and depth at most twelve and the neural model uses 96 and 32 hidden units. Held out forest accuracies range from 95.56 to 97.33 percent and neural accuracies range from 96.89 to 97.11 percent. These are workload checks and not classification improvements.

| Estimator | Bound | Snapshot saving | Robust exact requests |
|---|---:|---:|---:|
| forest | 1 | 90.63% | 32/32 |
| forest | 2 | 81.65% | 56/56 |
| mlp | 1 | 36.36% | 32/32 |
| mlp | 2 | 0.00% | 56/56 |

### Native DVC snapshot comparison

The native DVC experiment completes 40 real per version checkouts across 6 separately captured history configurations and checks every restored model and prediction hash. The following means use two seeds and include common roots and manifest and contract bytes while DVC specific directory and pointer bytes are recorded separately.

| Workload | Bound | Normalized DVC snapshot bytes | RecoverML bytes | Saving |
|---|---:|---:|---:|---:|
| logistic | 1 | 149614 | 84914 | 43.24% |
| logistic | 2 | 149614 | 128730 | 13.96% |
| forest | 1 | 10241524 | 959842 | 90.63% |
| forest | 2 | 10241524 | 1878866 | 81.65% |
| mlp | 1 | 1508949 | 960343 | 36.36% |
| mlp | 2 | 1508949 | 1508949 | 0.00% |

![Normalized storage and native snapshot validation](../results/research/paper_oct14/analysis/dvc_storage.png)

### Exact planning scalability

All 60 planner executions match the independently derived byte minimum. Timing repetitions per formulation and case rotate the solve order and the times include formulation construction and solving and post checks. These are same host repeated timings rather than independent machine samples.

| Groups | Bound | RecoverML median ms | Expanded median ms | Expanded / RecoverML |
|---|---:|---:|---:|---:|
| 6 | 1 | 25.58 | 10.41 | 0.41 |
| 6 | 2 | 34.03 | 31.00 | 0.91 |
| 12 | 1 | 25.94 | 17.84 | 0.69 |
| 12 | 2 | 27.07 | 132.28 | 4.89 |
| 24 | 1 | 26.99 | 34.57 | 1.28 |
| 24 | 2 | 29.86 | 680.10 | 22.78 |

![Both exact formulations and their total planning time](../results/research/paper_oct14/analysis/planning_scaling.png)

At 24 groups and two losses the expanded model has 27255 variables while the storage master has seventeen and the adversary has forty one. The master and adversary are solved iteratively and these counts should not be interpreted as a single seventeen variable full optimization. Enumeration is faster in the smallest cases and the proposed advantage emerges as the scenario universe grows.

### Indexed certificate kernel

| Generated depth | Scan median ms | Index median ms | Kernel speedup |
|---|---:|---:|---:|
| 32 | 0.439 | 0.110 | 4.00 |
| 128 | 7.631 | 0.294 | 25.98 |
| 512 | 148.777 | 1.638 | 90.81 |
| 2048 | 2493.473 | 5.734 | 434.89 |

![Certificate kernel scaling](../results/research/paper_oct14/analysis/certificate_index.png)

All 56 kernel timings preserve the complete certificate including producer choices and grounding rounds. The generated dependency chain result measures certificate construction only and is not a claim of the same speedup for a full model recovery request.
