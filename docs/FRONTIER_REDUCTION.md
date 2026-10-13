# Exact replayability frontier reduction

## Formal model

Let the captured pipeline be a finite directed acyclic graph G equals V E
Each node v has one content addressed output blob b of v and a nonnegative replay cost c of v
Each blob has a byte size and the retained set S must satisfy one global storage budget after mandatory source blobs and metadata are counted
A protected request names one or more target nodes

A node can be produced by loading its blob when the blob is in S or by executing the node when its replayability contract is true and all parents can be produced
The executor is load first so it never replays a node whose blob is retained
The objective is the sum of modeled loading and replay costs across protected requests

## Problem

RecoverML chooses physical artifacts to retain under a byte budget
Each protected historical version must be restored by loading retained artifacts or replaying supported operators
The runtime is load first so a retained output is loaded and its parents are not evaluated
An opaque output is not replayable and therefore it must be loaded whenever a recovery path reaches it

## Replayability frontier

For one protected version start at every target and walk backwards through dependencies
Include every visited node and continue through its parents only when that node is replayable
Stop when a non replayable node is reached
The union of these stopped walks across all protected versions is the live frontier subgraph

Content addressed blobs shared with a live node remain eligible even when another occurrence is outside the frontier
Mandatory source blobs also remain retained

## Reduction rule

Any optional blob that belongs only to nodes outside the live frontier is removed from the optimization model
Planner V4 also substitutes two kinds of fixed binary decisions

1. A mandatory source storage variable is fixed to one so its bytes move to the fixed side of the budget
2. A replay variable is fixed to zero for a non replayable node and for a node whose blob is mandatory because the runtime will load that blob

## Exactness argument

Consider the load first evaluation of any protected target
If its blob is retained then evaluation loads it and stops at that node
If it is not retained then the node must be replayable and evaluation recursively produces its parents
If the node is not replayable and not retained then that recovery is infeasible

Therefore evaluation can never cross backwards through a non replayable node
Every node that can be produced for a protected target is inside the live frontier subgraph
A blob used only outside that subgraph can never be loaded during a feasible protected recovery
Removing it cannot break a recovery path or increase replay cost and it can only release storage

The fixed variable substitutions preserve the same decisions because they replace values required by the mandatory input and load first contracts
Thus the original and reduced formulations have the same feasible protected recoveries and the same optimal objective under these contracts

## Theorem

For a finite acyclic graph with complete dependencies and correct replayability declarations and mandatory source retention and load first execution let F be the union of backward walks from every protected target where traversal stops after visiting a non replayable node
Removing an optional physical blob decision whose every occurrence lies outside F preserves the feasible retained sets after projection onto F and preserves the optimal protected recovery objective

### Proof

Consider one execution path for one protected target
At a visited node the executor either loads a retained blob and stops at that node or replays the node and visits all parents
A non replayable node cannot take the second case
Therefore no feasible target execution visits a parent solely through a non replayable node
By induction from each target every node that a feasible execution can load or replay belongs to F

A blob occurring only outside F cannot be read by a protected request and its retention cannot change whether any node in F is producible
Removing its decision therefore cannot remove a feasible protected execution
It also cannot increase the cost of one because that blob contributed no protected load or replay action
Conversely every retained set in the reduced problem is a retained set in the original problem after assigning removed optional decisions to zero
The projected feasible sets and objective values are equal and their optima are equal

Mandatory source storage variables may be substituted with one because the contract requires their retention
Replay variables for non replayable nodes and mandatory loaded nodes may be substituted with zero because those replay branches are forbidden by the contracts
These substitutions preserve every feasible assignment and objective value after projection

### Construction cost

The frontier is constructed with one reverse graph traversal and a visited set
Its time is O of V plus E and its memory is O of V
The reduction does not change the worst case complexity of the remaining mixed integer problem but it can reduce its variables and constraints from the whole captured graph to the live frontier

### Counterexample boundary

The theorem is invalid if a supposedly non replayable node is actually bypassed by an undeclared dependency or if execution replays retained nodes instead of loading them
It is also invalid when operator side effects affect a target without a recorded edge
These are contract violations rather than cases covered by the theorem

## Conditions

The argument requires an acyclic dependency graph and complete recorded dependencies and correct replayability declarations
It also requires the load first executor used by RecoverML and mandatory source retention and the same additive planning cost model
Hash verification checks the produced outputs but it does not prove that an operator contract was declared correctly

## Validation

The automated tests compare the reduced formulation with exhaustive enumeration on 12 generated graphs across four budgets each
They also compare Planner V2 and V3 and V4 on captured public data histories

The 10 October scaling study uses the Iris dataset and 15 independently captured histories and two budgets and five frontier depths
It contains 450 paired planner sets or 1350 planner executions and 120 separate exact restores
All 450 sets reached proven optima and produced identical objective values
At a frontier depth of 128 the model fell from 1256 variables in V2 to 69 variables in V4 which is a 94.5 percent reduction
The median history level V2 to V4 planning speedup was 3.38 times with a bootstrap 95 percent interval from 1.24 to 5.32
V4 was faster for 14 of 15 history comparisons and the one sided paired Wilcoxon result was p equals 0.0002136

These measurements establish the exact reduction and its local scaling behavior for the tested graph family
They do not by themselves establish that no earlier system uses an equivalent reduction

The 11 October wide topology study adds 15 executable histories and 315 planner executions
It covers graphs up to 1038 nodes and 1068 edges and completes 45 exact restores
Every solver run reaches a proven optimum and all V2 V3 and V4 objectives agree
The median V2 to V4 planning speedup is 10.47 times and the median variable reduction is 98.21 percent
In the largest topology the formulation falls from 7218 variables to 33 which is a 99.54 percent reduction
The stored values are small numerical arrays so this result establishes planner scaling and not deep learning training performance
