# Exact replayability frontier reduction

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
