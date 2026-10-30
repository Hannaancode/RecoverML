# Same-store retained-file recovery ablation

The final [GitHub Actions run](https://github.com/Hannaancode/RecoverML/actions/runs/41044852911) on source commit `9d830e28696be54a41c0c4068c5bb7ecf166542b` completed on 30 October 2026. The retained `evidence.zip` has SHA-256 `e63c3c104c29683d56580de22f55203a6eb152d1be4b2374b991cf35ef0732a6`. Run `python scripts/audit_retained_file_ablation_release.py` from the repository root to check the archived logs, paired order, source commit, summaries, and exact target hashes.

Each case uses the same selected physical files and target requests for all three internal paths: direct retained-file export, graph/contract setup followed by export, and that same setup/export followed by deserialize/repack and a source reread. The third path is additive, so its difference is not a pure CPU serialization cost. The fixed protocol uses Breast Cancer and Digits, 1/4/16 versions, three repeats, 64 paired requests per repeat, fresh private output paths, and rotated arm order. Warmup and capture are outside the timed region; OS caches were not flushed. The archive contains request-level timings, source hashes, captures, environment information, and the audit.

| Case | Setup/export to direct median paired ratio | Conversion to setup/export median paired ratio |
| --- | ---: | ---: |
| Breast Cancer, 1 version | 3.729 | 1.174 |
| Breast Cancer, 4 versions | 3.706 | 1.171 |
| Breast Cancer, 16 versions | 3.715 | 1.148 |
| Digits, 1 version | 2.749 | 1.549 |
| Digits, 4 versions | 2.787 | 1.529 |
| Digits, 16 versions | 2.885 | 1.465 |

All **3,456/3,456** requests recovered exactly. Direct export beat setup/export in **1,152/1,152** paired requests, with a **3.33×** median paired ratio across requests. Setup/export beat the added conversion path in **1,134/1,152** requests, with a **1.32×** median paired ratio. All 18 workload-length-repeat groups had the same ordering by group median. These results explain internal fast-path overhead on the measured CI host. They do not compare RecoverML with an external system or alter the established equal-storage ties.
