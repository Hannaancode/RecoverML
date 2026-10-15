# Run the retinal study from start to finish

The study uses a CPU and does not need a GPU. It constructs recorded histories on the 20 public STARE retinal photographs. It does not reproduce EyeAI patient data or its glaucoma models.

## Prepare the software

Use Linux or WSL2 and Python 3.12. Create a virtual environment from the repository root and install the pinned dependencies.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
```

There is no need to install PyTorch for this experiment. Direct dependency versions are fixed in `requirements.txt`. Existing stored results also record exact source hashes and the complete environment contract. Matching dependency versions alone does not guarantee that another Python patch version or numerical environment produces identical historical bytes. The replay code checks that contract and fails if it differs. Fresh capture and replay on another host tests reproduction in that host's own environment and should be described separately from replaying this host's original stored bytes.

## Acquire the complete image set

```bash
python scripts/download_stare.py --destination work/stare --report results/research/eyeai_rebuild_oct15/data_acquisition.json
python -m unittest tests.test_eyeai_workflow -v
```

The downloader obtains every image and every Adam Hoover label from the pinned research repository commit. It verifies all 40 Git blob hashes and writes their URLs and SHA-256 hashes. The image data remain in `work/stare` and are not used to select favorable recovery settings. The two tests check that the feature revision changes actual bytes and that both feature revisions and their models replay exactly from roots.

## Run a small check

Use a new output directory. The runner refuses to overwrite an existing result.

```bash
python -m recoverml.eyeai_experiment --output results/validation/eyeai_my_preflight --preflight
python scripts/analyze_eyeai.py results/validation/eyeai_my_preflight
```

The preflight has two historical forest versions and one target mode and one availability contract and five methods. It performs 20 actual recovery requests and four native DVC checkouts. It is a functionality check rather than the full result set.

## Run all declared experiments

Read `docs/EYEAI_PROTOCOL_OCT15.md` and the configuration before starting.

```bash
python -m recoverml.eyeai_experiment --output results/research/eyeai_my_full_run
python scripts/analyze_eyeai.py results/research/eyeai_my_full_run
```

The full grid has 18 captures and 540 method rows and 10920 actual recovery requests. Native DVC executes 624 checkout commands. Native checkout hashes are checked once per historical version and target set and DVC policy. Those receipts are reused when the same snapshots are examined under different simulated capability losses. Reused receipts do not count as additional DVC executions.

The methods share their input artifacts and protected historical targets and fault assumptions. Common retained bytes include roots and original lineage metadata and the capability contract and the unique selected payloads. DVC cache object overhead and pointer files are additional reported fields. The direct snapshot read time and native CLI checkout time are separate measurements because a Python process starting DVC can dominate a tiny artifact read.

The raw request log records UTC start times and actual elapsed time and process CPU time and process I/O counter differences and target SHA-256 hashes and operator events. `max_rss_kib` is the cumulative maximum resident memory of the benchmark process and must not be interpreted as isolated memory allocated by that request. Timing uses one repetition per request and the host cache is not isolated.

`analysis.json` verifies the declared complete grid and reconciles CSV counts against every raw request. `RESULTS.md` reports both improvements and ties. `economics.csv` uses measured CPU costs and saved GiB-days without assigning made-up service prices. `plots/` contains storage curves and a latency CDF.

The complete final trace is `raw.jsonl.gz`. The original plaintext trace and append-only intermediate ledgers can remain local. Source files used at capture time are in `source_snapshot/` with `source_hashes.json`. A failed or interrupted attempt must remain a separate result directory and must not be described as a complete grid.

## Check native DVC replay after actual source retirement

After the full run has captured `forest_s3_v16` run the separate control.

```bash
python scripts/native_retina_repro.py --input results/research/eyeai_my_full_run --output results/research/eyeai_my_native_repro
```

The control creates ordinary DVC stages in `/tmp` and first replays from the original roots. It then keeps roots and one older feature output and removes the other workspace outputs and downstream cache files and the run cache. It physically removes the legacy feature Python entry point and checks that a fresh Python process cannot import it. The older feature stage is frozen and DVC replays downstream outputs. The entry point must still be absent after replay. A matching minimum frontier shows that DVC supports this manual choice. It does not establish a unique recovery ability for RecoverML.

The native control records every command and expected failure and hash. It reports separately whether its manual retained set equals RecoverML's certified minimum. The native command times include DVC and Python stage startup costs.

## Recover one packaged retained store

The final `stores_deduplicated.tar.gz` stores each unique original payload once and preserves all per-policy store memberships and original manifests. It does not change the retained bytes used in the experiment.

```bash
python scripts/restore_eyeai_store.py results/research/eyeai_my_full_run/stores_deduplicated.tar.gz forest_s3_v16__model_prediction__legacy_removed__RecoverML_exact work/restored_eyeai_store
```

The destination must not exist. Every extracted payload must match its original SHA-256. The archive includes capture manifests and all payloads needed to rebuild or inspect selected stores. Extract only known archive entries if inspecting it manually. Only trusted project stores may be decoded because the prototype's array serialization uses pickle.
