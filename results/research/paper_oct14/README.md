# Paper experiments

This folder keeps the final paper evidence together and the earlier milestone data remains separate
The complete local package contains every group below and the [publication record](../../../docs/PUBLICATION_PENDING_OCT14.json) lists compressed files awaiting public upload
Fresh reproduction creates its own evidence and saved-data analysis requires the complete raw input set

| Group | What is included |
|---|---|
| tabular | Initial corrected 48 case matrix and independent exact comparison with 28512 requests |
| estimators | Digits forest and canonical neural inference artifacts and eight cases and 1584 requests |
| published | Final fresh 56 case comparison with released HYPPO and the published HELIX rule and 33440 requests |
| fault_scope | Thirty six cases including training and prediction outages and 3920 exact requests |
| merged | One shared graph with 112 protected versions and 2464 exact requests |
| components | Layered AND controls with shared loss labels and 118 planning runs and 9288 exact requests |
| scaling | Sixty planner runs compared with an analytic minimum |
| index | Fifty six timing runs with identical complete recovery certificates |
| holdout | New group counts and widths and 108 exact planner validations |
| auto_real | Ten engine selector checks on original mixed graph manifests |
| analysis | Five original paper figures and their input and claim hashes |
| extension_analysis | Four final comparison figures and verified raw-derived claim tables |
| protocol_pilot | Earlier strict capacity protocol preserved and excluded from final claims |
| diagnostics | The initial failed neural serialization trial and original pilot stdout |
| source_snapshot | Exact recorded source versions used in each study |

HYPPO executes unchanged pinned materialization functions through our disclosed physical artifact adapter
HELIX executes our reimplementation of published Algorithm 2 and Definition 6 with a captured logical schedule and shared physical payload adapter
The main policies share the same robust byte limit and exact recovery executor
These are retention decision comparisons and not full native HELIX or HYPPO runtime comparisons
DVC performs native cache add and checkout and its system metadata is recorded separately from normalized payload accounting

Each report links its source identity and compressed raw logs and every selected store file is kept in stores.tar.gz where a store is used
The archive shares identical payload bytes through tar hard links and every path is verified against the original bytes
evidence_inventory.json records archive path counts and file hashes
tests_final.txt records 77 tests with 72 passing and five optional PyTorch skips
hardware.json records the measured CPU container and timing scope

Run fresh experiments with Python 3.12 and the pinned dependencies and choose a new destination

```bash
python -m pip install -e '.[paper]'
PYTHONPATH=src python -m unittest discover -s tests -v
bash scripts/run_paper_benchmarks.sh results/runs/my_paper_reproduction
```

Recreate figures from the saved evidence using new output folders

```bash
python scripts/analyze_paper_benchmarks.py --input results/research/paper_oct14 --output results/runs/review_main_figures
python scripts/analyze_retention_extensions.py --input results/research/paper_oct14 --output results/runs/review_extension_figures
```

Read the [paper](../../../paper/RecoverML_capability_loss.md) and [full simple summary](../../../docs/PROJECT_SUMMARY.md)

Replay a saved selected store with its exact recorded extension source and no recapture

```bash
PYTHONPATH=src python scripts/replay_paper_store.py --evidence results/research/paper_oct14/published --store digits-mlp-00-npy-k1/RecoverML_decomposed
```
