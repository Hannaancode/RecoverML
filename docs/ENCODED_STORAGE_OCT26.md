# Lossless storage and deterministic time travel: protocol, 26 October 2026

The native recovery census establishes a scoped DVC latency advantage. It does not establish superiority in storage.
An oracle supplied the exact optimum must tie RecoverML under identical representations and requirements.
This experiment tests a different engineering question: can the persistent store become materially smaller while every original canonical artifact remains recoverable byte for byte?

## Fixed population and gate

Use the entire earlier six-dataset/four-recipe catalogue, history lengths 1/4/16 and all three loss contracts: 72 fresh captures and 216 storage conditions.
Every permitted loss set is exercised, requesting all protected historical model/prediction files in each request.
There are seven scenario requests per capture per method, and nine methods, hence 4,536 actual requests.
The exactness gate requires every request of all six robust methods to succeed with original hashes.
The engineering storage gate requires at least 10% smaller complete stores than the raw exact frontier in at least 90% of conditions within every dataset, recipe and loss stratum.
Every failure, nonwin and adapter block remains in the denominator.
The machine-readable protocol is `configs/encoded_storage_oct26.json` and is frozen before the full run.

This gate concerns the existing uncompressed store. The stronger gzip and same-codec controls below must accompany it.
No gain over gzip, a manual optimum, or all established systems is assumed.
This is an authored finite catalogue, not a random production population.

## Representation and accounting

Canonical artifact bytes and SHA-256 identities are unchanged.
Adaptive encoding chooses the shortest of raw, zlib level 9, XZ preset 6, and gzip level 9, with a fixed reversible eight-byte shuffle also permitted.
This uses established compressors and the established byte-shuffle idea, rather than a new compression algorithm.
The stronger gzip control chooses between shuffled and unshuffled gzip level 9 for every file.
The standard shuffle concept is described in the [h5py documentation](https://docs.h5py.org/en/stable/high/dataset.html#shuffle-filter).
The decoder uses bounded [Python LZMA decompression](https://docs.python.org/3.12/library/lzma.html), stream completion checks and original size/hash verification.

A compressed metadata file retains the original graph/environment and declared loss contract.
Each retained artifact is one regular file with a one-byte mode prefix; its filename retains its original content hash.
All headers, roots, mode bytes and metadata count toward the sum of persistent file lengths.
This metric excludes filesystem directory/block allocation overhead, as in the earlier byte accounting.
Setup/capture oracles are not recovery sources. Recovery reads only the selected encoded store and surviving operators; no plaintext mirror is created.
Decoded requested output files, RAM used during replay and compression CPU cost are separate costs and cannot be presented as zero.
Decoder availability is part of the format contract; surviving model replay still requires the original supported runtime.
Retained-file export asserts original file bytes rather than cross-version model execution compatibility.

Selection uses a cost-only graph with encoded byte lengths, preserving all IDs, dependencies, roots and targets.
The executable graph retains original canonical sizes. The two graphs must never be confused.
Metadata size is constant across selections for a condition, so minimizing encoded payload costs minimizes the complete store.
Independent scenario exact optimization must match each raw/gzip/adaptive exact byte optimum.

## Comparators

Raw exact writes the original store format. Gzip exact uses the stronger gzip representation and reoptimizes selection.
Adaptive exact, strong local search, target snapshots and all published-component adapters receive the same adaptive representation.
An adaptive raw-choice control compresses the old raw optimum without reselecting, separating representation benefits from decision changes.
The manual oracle is a storage control supplied the independent exact optimum, so its byte result must tie rather than become a manufactured win.
The HYPPO rank/frequency components and HELIX rule receive the same optional budget as the adaptive optimum; they remain component/rule adapters, not full native systems.
All six robust controls recover through the same conditional exactness requirements. Expected adapter blocks are reported separately from unexpected errors.

## Execution and durable evidence

A separate one-history acceptance job checks every method and loss before 24 full dataset/recipe jobs start.
Acceptance timings/results are excluded from the primary catalogue.
Save source snapshots, canonical capture manifests, all encoded candidate bytes, actual selected-store file inventories,
exact solver/heuristic selections, all loss certificates, output hashes and operation traces.
An independent audit reconstructs byte objectives and request denominators without fitting models.
Archive encoding may differ across library releases, so audits verify original saved encoded bytes rather than substituting newly compressed files.
Original failed attempts are preserved and are not overwritten by a favorable rerun.

The earlier 230 frozen storage conditions will also receive a separately labelled byte-level transfer audit.
Missing candidate payloads, including the incomplete large Letter archive, must appear as unavailable records; they are not silently excluded or replaced by hypothetical compression ratios.
Frozen-byte checks are distinct from fresh end-to-end replay under the current runtime.

## Using the format

For a complete raw capture and its declared capability contract:

```sh
PYTHONPATH=src python -m recoverml.encoded_store create --capture FULL_CAPTURE --contract CONTRACT_JSON --output NEW_STORE
PYTHONPATH=src python -m recoverml.encoded_store recover --store NEW_STORE --output NEW_OUTPUT --operators census --disable preprocessing
```

Choose the operator family that produced the capture and an output directory outside the persistent store.
Fresh writes refuse an existing destination. The Python API also accepts an explicit supported replay callback.

## Completed evidence and stronger baseline

The [complete results](../results/research/encoded_storage_oct26/RESULTS.md) retain all 216 fresh conditions and all 230 older transfer conditions.
The fresh engineering gate passes with at least 35.96% raw-byte savings everywhere and 504/504 adaptive-exact recovery requests.
After execution, the gzip control was strengthened to permit raw fallback; this is a disclosed additional byte-level exact control and adds no model-replay requests.
It gives 9.80% median saving, with only 106/216 reaching 10%. Manual same-codec optima still tie.
The original frozen execution protocol and raw results are unchanged.
