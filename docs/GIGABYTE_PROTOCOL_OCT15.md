# Frozen larger storage study

The study uses the official UCI Letter Recognition data with all 20,000 rows and 16 features and 26 classes. The data are image-derived character features rather than clinical data. The official dataset page is https://archive.ics.uci.edu/dataset/59/letter+recognition and the source DOI is 10.24432/C5ZP40 and the license is CC BY 4.0.

A useful research activity is keeping a complete classifier tuning history so an older fitted model or its held-out predictions can be investigated later. We use a fixed 16-model grid with 64 and 128 and 192 and 256 trees and two feature-sampling settings and two random seeds. No file padding or artificial model duplication is allowed and no extra configurations will be added after looking at storage savings. The fixed split seed is 20261015 and the stratified test fraction is 0.25 and the actual split is checked to be 15,000 training rows and 5,000 test rows. MinMaxScaler and SelectKBest with chi2 and k=12 are fitted only on training data. All sixteen models and their actual predictions are protected regardless of accuracy.

The objective is minimum retained canonical artifact bytes for exact recovery after loss of at most one declared processing capability. The preprocessing scope and broad scope are both tested. Broad scope includes training and prediction loss and can legitimately save nothing. The main methods are RecoverML exact and an independent scenario-expanded exact formulation and a direct robustness-aware greedy baseline and its local-improvement version and complete target snapshots. The common budget is mandatory roots plus every target snapshot plus the same manifest and failure contract. Partial greedy results are recorded as partial instead of being discarded.

The allowed k=1 scenarios are all checked structurally. Actual disk recovery is run for every historical version for every distinct selected physical store under loss of all preprocessing groups at once including membership. This deliberately stronger stress is labelled separately from the allowed k=1 contract. Identical store and outage pairs share runtime measurements and are not counted as separate actual requests. Recoveries start with an empty capture archive and selected files only and exact output hashes are checked. Unexpected failures are distinguished from declared structural impossibility.

A real native DVC command control adds every unique canonical target file and removes the workspace copies and checks them out again and verifies every file by SHA256 and exact byte length. Hard links keep the workspace within resource limits and logical stored payload accounting is separate from shared physical inode allocation. DVC startup timing is reported separately from in-process recovery.

Every canonical payload is also actually gzip-compressed at level 6 and the compressed bytes and hashes are logged. Native sklearn protocol-5 model pickle sizes and compressed sizes are separate representation controls because the canonical JSON and base64 model codec can be larger. A one-gigabyte reduction in uncompressed canonical bytes is not automatically a one-gigabyte reduction in compressed or native pickle files. These comparisons will all be shown even if they miss the requested one-gigabyte goal.

The raw large capture files stay under the ignored work directory. The source and fixed protocol and all receipts and a small exact preprocessing frontier are saved with the project. The analyzer independently checks the entire declared model and method grid and hashes and storage accounting and all allowed-scenario certificates and actual runtime request identities and native DVC file dictionary. Passing the large storage goal is not evidence of a new optimization theory and the simple shared feature frontier may match our certified result.

The small two-model protocol with 2 and 3 trees is an execution preflight only. It is not a large storage result. The full experiment is not started until the earlier scientific matrix and retinal workflow are complete and verified.

Run from the repository root using the pinned CPU environment:

```
PYTHONPATH=src python scripts/gigabyte_history.py --protocol configs/gigabyte_letter_preflight_oct15.json --output results/validation/2026-10-15/gigabyte_preflight --work work/gigabyte_preflight
PYTHONPATH=src python scripts/analyze_gigabyte_history.py results/validation/2026-10-15/gigabyte_preflight --verify-payloads work/gigabyte_preflight
```

After the earlier validations are complete the main commands use configs/gigabyte_letter_oct15.json and results/research/gigabyte_letter_oct15 and work/gigabyte_letter_oct15. The output and work paths must be new so an interrupted run cannot silently overwrite an earlier outcome.
