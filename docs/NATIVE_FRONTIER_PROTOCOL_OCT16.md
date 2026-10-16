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
