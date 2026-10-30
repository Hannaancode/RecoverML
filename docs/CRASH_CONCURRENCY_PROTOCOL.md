# Store publication and concurrent recovery protocol

## Scope and invariants

The new `recoverml.store_publish.publish_store` path publishes one immutable
selected store on a single filesystem. A caller assigns one publisher to each
destination. Readers open only the final directory, never a sibling whose name
starts with a dot and contains `.staging-`.

1. **Before publication:** all selected blobs, the manifest, and any contract
   files are written in a new sibling directory. Each file is flushed and
   `fsync` is called. On POSIX, the staging directories are also synced.
2. **Publication:** the complete staging directory is renamed to the final
   destination on the same filesystem. The parent directory is synced on
   POSIX after rename. An existing final destination is refused.
3. **Recovery:** a request reads the final store without modifying it. Every
   request owns its restorer, memo, trace, and output directory. Returned
   target bytes must match the captured SHA-256 identity.
4. **Failure:** a process exit before rename leaves no final store. A process
   exit after rename leaves a complete final store. A staging directory left
   by a crashed publisher is an orphan; an operator can remove it after
   confirming that the publisher has stopped. A crashed request has no
   successful receipt and its request-specific output can be discarded.

The `verify_published_store` check compares the complete selected blob
inventory, lengths, and hashes with the manifest. The caller records the
selected set separately so a missing blob cannot be hidden by a valid
manifest alone.

## Executable evidence

`tests/test_store_publication.py` launches child processes that call
`os._exit(47)` immediately before and after rename. It checks the resulting
final paths and runs 32 concurrent readers against a complete store with
isolated outputs. The cloud workflow reruns these checks on Linux.

`scripts/benchmark_runtime_scaling.py` tests the final file recovery API on
two public datasets, three version counts (1, 4, 16), two retention modes,
1/2/4/8 threads, and 1/2/4 independent same-host process replicas, with three
repeats and 128 requests in each cell. The full matrix has 252 trials and
32,256 requests. It retains every request's latency, expected and observed
target hashes, timestamps, source hashes, configuration, and hardware
metadata. The independent audit recomputes the grid, exactness, throughput,
P50, and P99 from raw requests. `root_replay` retains only mandatory roots;
`target_files` also retains protected target files. These are runtime
retention-mode controls, not claims that either mode has the same byte cost.

The thread sweep measures queueing and shared runtime contention. The
process-replica sweep measures capacity on one host; it does not implement
networked requests, shared mutable state, cross-machine coordination, or a
distributed crash protocol. The byte stores are read-only after publication;
output directories are request-specific. Process crash checks do not simulate
loss of power or disk hardware. The original `write_store` remains available
for legacy benchmark staging and older artifacts, so the publication guarantee
applies when callers explicitly use `publish_store`.

## Reproduction

On Linux with Python 3.12, from the repository root:

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests -p test_store_publication.py -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src \
  python scripts/benchmark_runtime_scaling.py --output work/runtime_scaling_full
PYTHONPATH=src python scripts/benchmark_runtime_scaling.py --audit-only \
  --output work/runtime_scaling_full
```

Use a fresh output directory for each run. GitHub Actions workflow
`.github/workflows/runtime-scaling-oct30.yml` executes the same commands and
uploads the raw run and machine metadata, including failed runs for inspection.
