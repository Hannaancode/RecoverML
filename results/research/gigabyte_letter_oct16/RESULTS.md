# Fixed UCI Letter history storage experiment

All 20,000 observations are used and preprocessing is fitted only on 15,000 training observations and predictions are evaluated on 5,000 held-out observations.
This is an executable constructed hyperparameter tuning history with genuine trained forests and no padding or duplicate model payloads.

Validation: **PASS** and 16 actual trained model versions.
Actual replay requests: 48 and exact: 48 and expected blocked: 0 and unexpected: 0.
Replay uses every version under all preprocessing groups disabled which is a stronger stress than the allowed k=1 contract and the k=1 claims are checked separately by complete structural enumeration.
Methods with identical selected payloads share runtime evidence and those requests are counted once.

| Scope | Snapshot bytes | RecoverML bytes | Saved bytes | Gzip saved bytes |
|---|---:|---:|---:|---:|
| preprocessing | 3,669,545,821 | 4,829,269 | 3,664,716,552 | 290,607,161 |
| broad | 3,669,548,445 | 3,669,548,445 | 0 | 0 |

| Scope | Method | Retained bytes | Complete allowed requests | Planning seconds |
|---|---|---:|---:|---:|
| preprocessing | RecoverML_exact | 4,829,269 | 64/64 | 0.021091 |
| preprocessing | scenario_exact | 4,829,269 | 64/64 | 0.009831 |
| preprocessing | robust_greedy | 4,829,269 | 64/64 | 0.037875 |
| preprocessing | robust_local | 4,829,269 | 64/64 | 0.044903 |
| preprocessing | target_snapshots | 3,669,545,821 | 64/64 | 0.000001 |
| broad | RecoverML_exact | 3,669,548,445 | 96/96 | 0.010681 |
| broad | scenario_exact | 3,669,548,445 | 96/96 | 0.009819 |
| broad | robust_greedy | 3,267,099,280 | 95/96 | 0.434660 |
| broad | robust_local | 3,669,548,445 | 96/96 | 0.462974 |
| broad | target_snapshots | 3,669,548,445 | 96/96 | 0.000001 |

Accuracy range: 0.95 to 0.9564

The uncompressed canonical model identity is the main contract and gzip level 6 is measured on every actual payload. The separate native sklearn pickle control is included in analysis.json because canonical JSON/base64 serialization can be substantially larger than native pickle.
A GB reduction in uncompressed canonical bytes does not imply a GB reduction in compressed files. Both outcomes are reported separately.
A simple manual choice of a shared recoverable feature frontier can match an exact optimizer on this workflow and this experiment alone does not prove that optimization is necessary.
Native DVC is tested with actual add and deletion and checkout and every unique target file hash is checked. DVC command startup is separate from in-process recovery timing.
The broad-failure condition is retained even when it saves no storage because training or prediction loss can require their target snapshots.
One CPU host and one replay per unique store and version are used and histories share a dataset so raw requests are not independent statistical samples.

Raw large payloads are reproducible from the fixed source and protocol but are not committed. The small exact preprocessing frontier and all selected-set identities and command receipts are included.
