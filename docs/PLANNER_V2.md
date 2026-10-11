# Planner formulations and limits

The new policy keeps the original executor and correctness contract. Each
restoration reads only its selected disk store, resets its in-memory memo,
loads a retained artifact whenever available, and otherwise replays declared
supported operations. Loaded and replayed artifacts both undergo hash checks.

## Guarded shortcut

Let `T_v` be the distinct requested nodes of version `v`. Every valid plan must
produce each such node. Define the load estimate `a_n = 20e-6 + size_n / 500e6`
and the recorded operation cost `c_n`.

If all direct targets plus required input history and metadata fit the budget,
and `a_n <= c_n` for every replayable requested node, retaining these targets
attains the lower bound `sum_v sum_{n in T_v} a_n`. Replaying a target already
costs at least `c_n`, before its dependencies. A non-replayable target must be
loaded. Repeated targets in one request are counted once, as in the executor.

This proof concerns the stated additive cost model. Deserialization, replay
serialization, hashing, OS cache behavior and scheduling can make actual
elapsed times differ. The shortcut does not claim minimum retained bytes among
equal-cost solutions; mandatory inputs remain retained even when target loads
would avoid them.

## Global optimization

For physical blob `b`, binary `x_b` means retain it. For each protected version
and ancestor node, binary `l_vn` and `r_vn` mean load or replay it. We minimize

`sum_vn (a_n * l_vn + c_n * r_vn)`

subject to these constraints:

- Serialized retained blobs plus metadata fit the declared byte budget.
- Required input blobs have `x_b = 1`.
- Requested nodes have `l_vn + r_vn = 1`; other nodes have this sum at most 1.
- `l_vn <= x_blob(n)`.
- Non-replayable nodes have `r_vn = 0`.
- `r_vn <= 1 - x_blob(n)`, matching the load-first executor.
- A replayed node requires every parent: `r_vn <= l_vp + r_vp`.

Physical deduplication is represented by one retention variable per blob.
Sharing inside a version request is represented by one node-production pair.
Different version requests have fresh memoization and separate costs.

SciPy's `milp` wrapper invokes HiGHS. The solver time limit is 0.5 seconds;
matrix construction, imports and postchecking are additional planning time.
Solver status 0 establishes optimality for this model; status 1 may provide a
feasible incumbent without that guarantee. Status 2 reports model infeasibility.
Every incumbent is checked against integer byte accounting, dependency
coverage and the executor's independently calculated estimated cost. Unused
optional blobs are removed. If no valid incumbent is returned, v1 is the
fallback. Its failure remains a heuristic failure.

Zero replay costs, shared ancestors, overlapping targets, non-replayable
boundaries and below-minimum budgets are covered by exhaustive reference tests.
These tests do not establish cross-environment numerical reproducibility or
dependency completeness for arbitrary Python code.

## Planner V3 and V4

Planner V3 computes the replayability frontier before building the MILP
Its backward target walk stops at a non replayable node because the load first executor must load that node and never evaluates its parents for that recovery path
Artifacts that occur only behind the stopped frontier are removed from the formulation while shared artifacts used by a live node remain eligible

Planner V4 keeps the same frontier and also removes fixed binary variables
Mandatory source storage decisions are replaced by fixed byte cost and replay variables fixed to zero are removed for non replayable nodes and mandatory blobs
The [frontier reduction note](FRONTIER_REDUCTION.md) gives the exactness argument and conditions

## Research interpretation

Budgeted artifact retention and global load/recompute planning already have
substantial prior work. HELIX describes an optimal reuse formulation and an
NP-hard materialization problem. Our bounded MILP is an implementation choice,
not a new optimization primitive. The fast shortcut removes avoidable work
when a strong simple baseline already attains our estimated lower bound.

The narrower research question is whether an exact replayability frontier can reduce budgeted recovery planning work while preserving the same protected recoveries and objective
The 10 October experiment provides scaling evidence for this question while the broader novelty comparison with published systems remains part of the paper work

Primary references:

- [SciPy MILP API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)
- [HELIX paper](https://www.vldb.org/pvldb/vol12/p446-xin.pdf)
