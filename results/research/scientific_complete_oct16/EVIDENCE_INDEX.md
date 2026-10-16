# Completed scientific grid

The independent raw analyzer passes all 1920 declared conditions and 36480 actual requests from eight constructed public-recipe histories
Both exact formulations prove the same minimum in all 48 cases and there are no unexpected recovery outcomes

## Resumption and evidence

- `retry_protocol.json` fixes the rule that rejects any case with a source guard flag or an incomplete raw identity grid or mismatched measurements
- Eight source-flagged forest cases were rerun and four clean forest cases were reused
- Six complete nonforest histories were selected by the complete declared identity grid and their measured latency and CPU and I/O summaries reconcile
- `superseded_attempts.tar.gz` preserves the original unfinished run evidence and all first forest attempts including their source flags
- `accepted_case_evidence.tar.gz` preserves each accepted forest case raw log and summary and actual run-start metadata and planning outputs
- `accepted_case_evidence_index.json` lists every archived accepted file and its SHA256
- `source_versions.tar.gz` preserves the actual source versions for the original run and every accepted forest case
- `captures.tar.gz` preserves all eight frozen input stores
- `retry_worker_logs` records commands and start and end times and exit codes for the eight new workers
- `analysis.json` records exact request identities and count and measured-metric reconciliation across the entire final grid

The interrupted original process lacks a closed global source guard for its six reused nonforest histories
Their source snapshot and per-request operator and environment guards and complete raw reconciliation are preserved and this limit remains explicit

## Reading the comparisons

Exact retention minimizes the bytes needed for complete recovery under the stated loss contract
At budgets below that minimum it reports infeasibility and does not optimize partial recovery
The strong local baseline matches exact retained bytes in all 48 full-budget cases and gives more partial-budget recoveries in this fixed matrix
This experiment therefore supports correct exact minima and published-component comparisons but does not establish that exact optimization is necessary for these graphs

One trial per request and six workers sharing the host make timing and tail latency descriptive
There are eight constructed histories and repeated requests are correlated
This grid is separate from the compact fresh cloud reproduction and it does not test the original captured blobs on that second environment

## Commands

Run these from the repository root with its pinned dependencies installed
Use a new `/tmp` output directory for each attempt and keep all source modules unchanged while workers run

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python scripts/retry_scientific_matrix.py --output /tmp/recoverml_scientific_retry_NEW --prepare
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python scripts/retry_scientific_matrix.py --output /tmp/recoverml_scientific_retry_NEW --run-cases
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python scripts/retry_scientific_matrix.py --output /tmp/recoverml_scientific_retry_NEW --merge-to /tmp/recoverml_scientific_complete_NEW
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python scripts/analyze_scientific_audit.py /tmp/recoverml_scientific_complete_NEW
```

The resumption commands require the preserved original attempt inputs identified by the protocol
For a fresh experiment use the full scientific benchmark runner and the original protocol rather than pretending new timings reproduce an old interrupted attempt
The additional accepted-case archive is a closed-file packaging step and changes no measurements
