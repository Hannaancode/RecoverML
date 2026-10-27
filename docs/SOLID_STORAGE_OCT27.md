# Executable joint-compression follow-up

This is a post-hoc engineering follow-up to the complete delta-storage study,
whose evidence is pinned at `6965f41cec4444eb41e135d1f04297bab24de340`.
The earlier solid-archive byte control exposed a large storage weakness. The
new implementation makes that exact archive layout usable for retained-file
export and guarded deterministic artifact replay. It does not introduce a new
compression algorithm or establish a globally optimal joint-compression plan.

## Storage and recovery

`python -m recoverml.solid_store create --capture CAPTURE --contract CONTRACT
--output STORE` compares three complete persistent stores: the adaptive flat
optimum, the single-base delta optimum, and joint compression of the flat
optimum's retained set. All metadata and retained roots count. It writes the
smallest actual byte count, with the same canonical artifact hashes.

Use `python -m recoverml.solid_store recover --store STORE --output OUTPUT`
with the relevant `--operators` and `--disable` options for replay. Retained
exports need no ML imports. Replay uses the existing environment guard and
checks the final canonical bytes. Original events and side effects are not
reproduced.

The solid archive has an indexed, length-bounded, SHA-256-checked payload.
Metadata occurs either inside the archive or in one separate file, whichever
is smaller. Duplicate, unknown or malformed members, missing mandatory roots,
corrupt or trailing bytes, and conflicting metadata are rejected. The decoded
archive is limited to 2 GiB; this is an explicit prototype limit.

Opening a solid store decodes its complete retained payload into memory.
Replay writes a temporary identity-encoded retained store and removes it on
success or failure. Receipts expose decoded retained bytes and temporary
store bytes; these are logical byte counts, not peak RSS measurements. No
random-access, latency, memory, or compression-time advantage is claimed.

## Complete evaluation, including stronger controls

The follow-up keeps all 446 existing conditions and both unavailable Letter
conditions. It is exploratory and reuses the same captures. It is not a new
held-out sample or a new preregistered success gate.

`scripts/benchmark_solid_storage.py` authenticates the original inputs and
delta records against their published release identities. It constructs real
stores, reopens them, checks every selected canonical hash and allowed-loss
certificate, and exports retained protected targets. It requires the new
flat-selection solid store to reproduce the exact byte count and file hashes
of the earlier published control. This is not a full-grid model replay or
timing experiment.

The local-search baseline also receives joint compression of both its prior
flat selected set and its fresh delta-graph selected set, while retaining all
its earlier flat and delta options. Comparing only against its previous
per-file representation would overstate any advantage. Every win, tie, loss,
and unavailable condition must remain in the final report.

The three-candidate production choice is not guaranteed to beat this broader
local control: joint compression changes the selection objective. The exact
reference still cannot be strictly beaten under identical candidate rules.
Broad superiority remains unestablished until the complete results say
otherwise; successful unit tests alone do not establish it.

## Validation status

The initial 12 targeted tests passed, including exact exports without ML
imports, malformed archives, physical byte accounting, CLI selection, strict
replay for four recipe families under three loss contracts, and regressions
for the existing flat/delta stores. A nine-condition PCA pilot reproduced
the original solid-control inventories. The complete source-pinned cloud
follow-up is required before publishing final aggregate performance claims.
