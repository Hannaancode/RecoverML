# When robust retention reduces to an ordinary minimum cut

This is a necessity challenge for the current research claim. It changes no planner or benchmark source and runs no new timing study. The derivation below is checked by independent finite enumeration. It is not presented as a new general min-cut algorithm or as a confirmed new theoretical discovery.

## Main finding

For a physical dependency DAG in which every nonroot artifact has at most one replayable producer the complete-recovery storage problem is much simpler than the general AND/OR problem. Once any single declared capability group may fail a fixed store protects the targets against every allowed bounded group loss if and only if it protects them when every grouped producer is unavailable at once.

In that subclass the minimum optional retained payload is an ordinary weighted vertex cut. Integer programming and counterexample-guided search are sufficient implementations but are not necessary to solve this subclass. Adding more versions or larger models can increase the byte savings without creating a harder optimization problem.

## Exact assumptions

Let B be the finite set of physical captured artifacts and let R be intact mandatory retained roots and let T be the protected targets. A selected store S contains R. Each physical artifact outside R has zero or one replayable producer. A producer can require several inputs and all inputs are required. It may be ungrouped or belong to one declared capability group.

After roots are treated as fixed available values the directed dependency graph is acyclic. The graph has an arc from each dependency artifact to its producer's output. Nonreplayable provenance nodes are not extra producers. Multiple logical nodes with one physical output can therefore violate the assumption if more than one is replayable.

The allowed failures are every subset of declared groups of size at most k. Retained payloads and roots remain available under these failures. The objective charges a nonnegative byte weight for each retained physical artifact and fixed manifest and capability-contract costs. Replay runtime and a recovery deadline are not part of this particular objective.

## 1 Universal group loss collapses to disabling all grouped producers

Write A_F(b) for the availability of artifact b under a disabled-group set F using grounded recovery from S. Let U(b) mean that b is available for every allowed F. Because the dependency graph is acyclic these values can be reasoned about in topological order.

If b belongs to S then U(b) is true because its retained file is intact.

If b does not belong to S and has no replayable producer then U(b) is false.

If b does not belong to S and its only producer belongs to a declared group g then U(b) is false for k at least 1. The allowed single failure F = {g} disables its only producer regardless of whether its inputs survive. There is no second producer to bypass that loss.

If b does not belong to S and its only producer is ungrouped with dependency set D(b) then

\[
U(b)=\bigwedge_{d\in D(b)}U(d).
\]

This follows because universal quantification distributes over the conjunction of required inputs. In particular the inputs do not get to choose different producers because each has at most one producer of its own.

These are exactly the availability rules after every grouped producer is disabled. Therefore for every fixed S and every k at least 1

\[
\bigcap_{F:\lvert F\rvert\le k}\operatorname{closure}(S,F)
=\operatorname{closure}(S,G),
\]

where G is the set of all declared groups. The right side is a reasoning device and need not itself be an allowed simultaneous failure. The equality implies the equivalence for protecting all targets.

An immediate consequence is that the minimum retained payload is unchanged as k increases from 1 to 2 or further within this subclass. Serialized contract metadata can still change with the numeric value of k and is paid separately. For k = 0 retain the original producer graph because no grouped producer is disabled.

## 2 Failure propagation becomes ordinary reachability

Disable all grouped producers when k is at least 1. Call an artifact a bad source when it has no surviving producer and is not a mandatory root. This includes opaque nonreplayable outputs and outputs whose only producer was grouped. For k = 0 only opaque outputs are bad sources.

Remove retained artifacts from failure propagation because their intact files make them available regardless of their producers. In a DAG an unretained artifact with one surviving producer is unavailable if and only if at least one required dependency is unavailable. Thus failure follows ordinary directed arcs from bad sources toward consumers.

Every unavailable unretained artifact is reachable from a bad source along these arcs. To see why trace an unavailable input backwards. A finite acyclic graph forces this trace to end at an unavailable artifact with no surviving producer. Conversely a bad-source path which crosses no retained vertex propagates unavailability along every arc.

Consequently S recovers every protected target if and only if its optional retained vertices separate all bad sources from all unretained targets. Retaining a target itself is allowed and cuts the path at that target.

## 3 Standard weighted vertex-cut construction

Mandatory roots are removed and paid once as a constant. For each remaining artifact b create two vertices b_in and b_out and an edge b_in to b_out with capacity equal to its captured payload-byte weight.

Create a super-source s and a super-sink t. Add an effectively infinite-capacity edge from s to b_in for each bad source. For every surviving producer add an infinite-capacity edge from each nonroot dependency d_out to its output b_in. Add an infinite-capacity edge from every nonroot target b_out to t.

For integer byte weights it is enough to use

\[
M=1+\sum_{b\in B\setminus R} w_b
\]

as the infinite capacity. Retaining all optional artifacts is feasible and costs less than M so an optimum never needs to cut one of those constraint edges.

A finite minimum cut can therefore select only the edges b_in to b_out. Its selected artifact weights are exactly the optional retention cost and the failure-path argument proves the equivalence in both directions. Add the mandatory root payload and fixed metadata costs after solving the cut. Zero-byte artifacts are valid zero-capacity cut choices.

The network has two vertices per optional physical artifact plus two terminals and its edge count is linear in artifacts and dependency incidences. Standard polynomial-time maximum-flow/minimum-cut algorithms solve it. This is a restriction of the current complete-recovery byte objective and does not solve additional recovery-time or partial-coverage objectives.

## Established methods and related database work

The vertex-splitting reduction for vertex capacities is textbook material. The [MIT 6.854 advanced-flow notes](https://courses.csail.mit.edu/6.854/16/Notes/n9-advanced_flow_algorithms.html) give this construction explicitly. The independent check script uses ordinary integer capacities and the established shortest-augmenting-path max-flow procedure. Neither is a RecoverML invention.

[HELIX Section 5.2](https://www.vldb.org/pvldb/vol12/p446-xin.pdf) already reduces its optimal execution-plan problem to project selection and maximum flow. Its separate storage-budget materialization objective in Section 5.3 includes materialization and future execution time. That is a different objective from this complete-recovery byte minimum. The tractable subclass here does not contradict its hardness result and should not be described as discovering min-cut optimization for ML workflows.

The [Horn-abduction reduction in our novelty review](NOVELTY_REVIEW_OCT15.md) describes the broader finite-scenario formulation. The result in this document identifies a simpler special case rather than establishing that the full general problem is easy or new.

## Independent finite validation

[audit_tractable_subclass.py](../scripts/audit_tractable_subclass.py) is a separate standard-library implementation of the generated graph specifications and grounded closure and max flow. It imports no RecoverML planner or certificate code and performs no artifact loading or timing measurement. The [validation receipt](../results/validation/2026-10-15/scientific_audit/tractable_subclass.json) records its source hash and every inspected capture-manifest hash.

The finite test enumerates all 2275 four-artifact DAG specifications with one mandatory root and all earlier-vertex dependency subsets and producer choices of no producer or ungrouped or group A or group B. Each of the eight possible retained sets is checked against the single-group intersection and the all-groups-disabled closure. This gives 18200 fixed-store closure comparisons.

It then checks every nonempty optional target subset with four nonnegative byte-weight profiles including a zero-byte profile. For both k = 0 and k at least 1 the max-flow cut is compared with an exhaustive search of all stores. All 127400 optimum comparisons agree and every returned cut store recovers the targets. This finite check supports the general proof but does not replace it.

## Actual new capture graphs

At the recorded inventory snapshot six of the eight public-recipe histories satisfy the stated single-producer physical-DAG assumptions. These are both Diabetes polynomial captures and both Digits PCA captures and both Digits forest captures. Both Iris captures have two replayable producers for one physically identical prediction output and therefore fail the sufficient uniqueness condition. Failing this condition does not establish that those two graphs are computationally hard.

All 11 retinal histories present at the first validation receipt satisfy the same graph assumptions. That is a snapshot while the declared 18-history retinal benchmark is still running and is not a declaration that its execution matrix is complete. The separate [retinal frontier analysis](EYEAI_FRONTIER_ANALYSIS.md) gives an even simpler closed-form comparison for the specific shared-feature structure.

The implication is substantial. The current real-image experiment can show useful storage sharing and exact recovery but its current topology does not establish that a general robust integer optimizer is needed. A later experiment saving more than 1 GB can still belong to this easy class. Model size and count alone are not evidence of interacting storage choices.

## Counterexamples outside the assumptions

### Two producers with different loss groups

A retained root r can produce target x through either producer A or producer B and both producers produce the same captured bytes. With k = 1 and neither x retained every allowed single loss leaves the other producer available. Disabling both groups at once loses x. The all-groups collapse is false here. This is the OR choice excluded by the single-producer assumption.

### An ungrounded physical cycle

Let a depend on b and let b depend on a through ungrouped producers. An unrelated mandatory root does not ground either artifact. Without retaining a or b grounded recovery fails. If a costs 3 bytes and b costs 5 bytes then recovering target a requires at least 3 bytes.

The naive failure-source cut has no opaque source for a or b because each has a producer. It incorrectly predicts a zero-byte cut. This is why the failure-reachability proof requires a DAG. The general RecoverML grounded certificate handles this cycle and does not treat it as a recovery path.

### Groups whose individual loss is not allowed

If a producer belongs to group B but the actual contract allows only loss of A then disabling B for the all-groups reasoning would be unjustified. The theorem explicitly requires that every declared group can fail by itself. Different outage families must be analyzed using their actual allowed sets.

## Research consequence

The implementation should eventually recognize this subclass if a fast-path extension is desired but no core source is changed by this audit. At present the result is a check on the necessity and novelty claim. The supported position is that RecoverML can automate and check retention under a precise contract and that several current experiments have simple exact solutions. A strong claim that realistic histories require the general optimizer still needs evidence beyond byte scale or a large number of independent branches.
