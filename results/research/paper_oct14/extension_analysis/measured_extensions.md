### Final published method comparison

The fresh matrix captures 28 histories and 56 bound cases and records 33440 real requests. Every main method has the same robust byte limit and exact recovery executor. HYPPO runs unchanged released ranking functions while HELIX is a documented reimplementation of Algorithm 2 and Definition 6 with disk speeds 50 and 200 and 800 MiB per second and both out of scope tie orders. These are decision rule comparisons and not native full system runtime comparisons.

| Policy | Exact | Requests |
|---|---:|---:|
| HELIX 200MiB capture | 1681 | 3344 |
| HELIX 200MiB reverse | 1681 | 3344 |
| HELIX 50MiB capture | 1940 | 3344 |
| HELIX 50MiB reverse | 1940 | 3344 |
| HELIX 800MiB capture | 1673 | 3344 |
| HELIX 800MiB reverse | 1673 | 3344 |
| HELIX snapshot budget | 2437 | 3344 |
| HYPPO frequency | 2291 | 3344 |
| HYPPO rank | 2240 | 3344 |
| RecoverML decomposed | 3344 | 3344 |

![Published methods at the common limit](../results/research/paper_oct14/extension_analysis/published_methods.png)

The HELIX snapshot budget row has the larger snapshot limit and is reported separately. The lossless subset below isolates actual outages because every main method recovers every no outage request. Rounded imports can additionally expose a difference between protecting all old targets and optimizing future reuse.

| Policy | No outage | One disabled group | Two disabled groups |
|---|---:|---:|---:|
| RecoverML decomposed | 320/320 | 960/960 | 480/480 |
| HYPPO rank | 320/320 | 729/960 | 278/480 |
| HYPPO frequency | 320/320 | 818/960 | 350/480 |
| HELIX 50MiB capture | 320/320 | 722/960 | 271/480 |
| HELIX 200MiB capture | 320/320 | 714/960 | 251/480 |
| HELIX 800MiB capture | 320/320 | 710/960 | 247/480 |

![Lossless outage effects](../results/research/paper_oct14/extension_analysis/lossless_outage_coverage.png)

### Shared history and physical decomposition

One graph combines 12 branches and 112 historical versions. Both original exact engines agree on both byte minima and complete 2464 exact disk requests. Ten component runs match those minima.

| Bound | Snapshot bytes | Minimum bytes | Saving | CE ms | Expanded ms | Decomposed ms |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 21376829 | 1390318 | 93.50% | 1408.24 | 152.44 | 98.31 |
| 2 | 21376829 | 3433246 | 83.94% | 6896.57 | 214.72 | 127.94 |

![Mixed real graph planning](../results/research/paper_oct14/extension_analysis/component_planning.png)

The original global CE uses 188 cuts at the two loss bound and is slower than expansion on this graph. The new exact component reduction removes independent retention decisions before local solving. These are separate timing phases on one host and descriptive medians rather than paired universal speedup estimates.

Twelve new layered AND controls with 10 and 20 and 40 shared groups and widths 18 and 28 complete 108 planning comparisons against an independent analytic minimum and all 9288 exact disk requests. CE alone is faster in some controls and decomposition has no universal speed guarantee.

### Broader training and prediction outages

A six history control has 36 scope and bound cases and 3920 exact disk requests. Decomposition and the independent expanded formulation agree on every byte minimum.

| Model | Bound | Feature losses saving | Also training loss | Also prediction loss |
|---|---:|---:|---:|---:|
| logistic | 1 | 43.24% | 37.24% | 0.00% |
| logistic | 2 | 13.96% | 8.14% | 0.00% |
| forest | 1 | 90.63% | 1.26% | 0.00% |
| forest | 2 | 81.65% | 0.00% | 0.00% |
| mlp | 1 | 36.36% | 8.53% | 0.00% |
| mlp | 2 | 0.00% | 0.00% | 0.00% |

![Broader outage storage](../results/research/paper_oct14/extension_analysis/fault_scope_storage.png)

The large forest saving relies on model fitting remaining replayable. When both fitting and prediction may fail the same store must survive either loss and every protected model and prediction must be retained in these captured graphs. Snapshots are then optimal even for a one loss bound. These are call restrictions with intact files and the recorded numerical environment and not package removal.
