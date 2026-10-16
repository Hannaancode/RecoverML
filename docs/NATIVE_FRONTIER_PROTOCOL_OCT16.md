# Fixed native frontier latency comparison

This exploratory follow-up is specified before executing the native comparison.
It follows the complete cloud storage comparison, which found a manual-frontier
tie. It seeks a separate practical latency advantage, not a lower storage cost.

The machine-readable protocol is `configs/native_frontier_latency_oct16.json`.
All two datasets, three seeds, three history sizes and both capture boundaries
are retained: 36 histories, with three randomized paired repetitions each.
Each history is captured fresh on its runner, with the pinned dependencies.

RecoverML and native DVC receive identical retained payloads chosen by the
certified optimum. This supplies DVC with the optimal frontier without charging
it selection time. DVC has one downstream batch stage and frozen retained
frontiers; it is not penalized by a separate Python startup for every model.
Both must supply identical target files, including every model and probability
array. Full snapshots need no recomputation when already retained.

The primary metric is median subprocess time to all verified target files,
including CLI bootstrap and common parent SHA256 verification. Setup, source
capture, lock construction and cache clearing are excluded and their commands
are retained separately. Worker core times and child CPU are secondary metrics.
Measurement-log writing is excluded. DVC uses copy cache and `--no-run-cache`;
all downstream cache objects are removed before every trial. Retained targets
are hard-linked into the output view of both methods to avoid extra payload
copies. OS page caches are not flushed. Orders are deterministically randomized.

The replay contract declares both preprocessing views unavailable. The DVC
frontier is frozen and a dispatched retired producer raises. The implementation
module is not physically deleted in this comparison; the earlier native retinal
control remains the physical-retirement evidence.

A result can establish latency of these authored integrations on these hosts.
CLI overhead, core replay and storage must be reported separately, alongside
every slower case. It cannot establish inherent DVC inferiority, universal
performance dominance, significance from independent workload samples or a new
optimization algorithm. Application priorities determine whether a latency
benefit matters more than another system's features.

Status at specification: implementation worker checks pass for exact recovery
and rejection of a missing retired view. Native DVC measurements are pending.
Raw commands and failures will be retained by GitHub Actions even on failure.

The first launch at source `b8ae201` failed before any timing trial because the
runner unpacked three capture return values into two variables. Run
38947760758 preserves the failed artifacts. This is a setup failure, not a
measured DVC loss. The fix changes no protocol condition or comparison metric.
A separately labelled Wine/16 smoke run precedes the complete grid and is
excluded from the full study's statistics.

Before admitting a final latency claim, the direct DVC batch is strengthened
to retain newly computed values in memory instead of serializing and then
deserializing them again. It still verifies the serialized output hash. This
removes avoidable baseline overhead without changing any case or metric.
Run38948170791 is retained as baseline v1; the strengthened baseline v2 must
complete a fresh full grid. These two executions must not be pooled.

Run38949922822 completed baseline v2. Inspection of its worker receipts showed
that clearing the entire native cache made DVC rerun even already-retained
targets. The final revision3 therefore permits native cache entries for paid
retained payloads, hard-linked to the same physical files. Every other cache
object and all run-cache entries are cleared. Distinct inode byte counts must
equal the paid payload bytes in both methods before each trial. This strengthens
DVC without giving it hidden downstream outputs or additional retained payload
bytes. Cases, repetitions and the primary latency metric are unchanged. Earlier
baseline versions are retained separately and do not supply the final headline.

Revision3 completed with18/18 RecoverML wins when recomputation was required,
median2.3256 times, and18/18 DVC wins when all target files were already paid
retained outputs. This complete mixed outcome is preserved. It motivated a
general production file-export path, `python -m recoverml.file_export`, which
verifies and copies already-retained target files without deserializing models
or importing numerical libraries. Missing target files fall back to the existing
replay path. The normal value-restoration environment checks remain unchanged.
Both worker integrations may use this same fast export; DVC may still skip its
worker through its paid native cache. Revision4 repeats the complete unchanged
case grid and latency metric with this engineering improvement. File export
does not assert that an exported model can be loaded in a different environment.
