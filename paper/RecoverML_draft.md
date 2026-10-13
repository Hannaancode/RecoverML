# RecoverML: Exact Replayability Frontier Reduction for Storage Budgeted ML Pipeline Recovery

## Abstract

Historical machine learning pipelines contain source data and transformed features and fitted models and predictions whose complete snapshots can require unnecessary storage while replay alone can fail at external or nondeterministic operations
RecoverML captures these artifacts in a content addressed dependency graph and chooses retained blobs under one byte budget and restores protected historical outputs by loading or replaying declared operators and verifies every result with SHA 256
This paper introduces an exact replayability frontier reduction for the load first recovery planner
The reduction stops backward optimization at non replayable outputs and removes physical and replay decisions that cannot affect a protected request
Exhaustive small graph tests and matched mixed integer programs preserve feasibility and optimal objective values
On 15 Iris histories the formulation at depth 128 falls from 1256 variables to 69 and planning is 3.38 times faster at the median while all 450 matched planner sets reach the same proven optimum
A separate wide topology study reaches 1038 nodes and reduces the largest model from 7218 variables to 33 with a 10.47 times median V2 to V4 speedup and 45 exact restores
A Digits multilayer perceptron study adds six neural histories and a genuine nondeterministic augmentation boundary and V4 restores all 63 admitted requests exactly
The results show that explicit replay contracts can remove irrelevant ancestry without weakening protected historical recovery under the stated execution model

## 1 Introduction

Machine learning development creates many related pipeline versions
Saving every intermediate artifact simplifies recovery but wastes storage and replaying everything saves storage but can be slow or impossible when a step depends on an unavailable service or unrecorded randomness
Existing lineage and materialization and notebook time travel systems establish the importance of reuse and checkpointing but a retained historical output needs only the portion of the captured graph that its execution can actually reach

RecoverML represents every captured operation and output as a node and records dependencies and parameters and replayability and a content hash
The planner chooses physical blobs under a byte budget and the restore engine loads retained values or replays supported operators
The executor checks the reconstructed serialization against the captured hash and fails closed when no exact path exists

The main contribution is an exact replayability frontier for a load first executor
When backward traversal reaches a non replayable node the output must be retained and its parents cannot be visited solely through that path
Removing that hidden ancestry from the optimization model preserves the feasible protected recoveries and their objective values

This paper makes four contributions

1. A storage budgeted recovery model with explicit replayability contracts and exact hash checked restoration
2. A linear time frontier construction and exact formulation reduction with stated assumptions
3. An implementation with automated raw traces and checksums and correctness tests
4. Evaluation on public tabular data and a CPU neural network and executable graphs up to 1038 nodes

## 2 Related work

HELIX optimizes reuse and materialization across iterative ML workflows and shows that graph based load and recompute choices are established prior work
LIMA adds fine grained lineage and reuse inside ML systems
Kishu and ElasticNotebook use dependency aware checkpoint and restoration for notebook state
ExoFlow uses task semantics including nondeterminism to support exactly once recovery in heterogeneous distributed workflows
FlorDB and Disdat capture ML lifecycle metadata and versioned artifacts
RecoverML does not claim to invent these mechanisms
Its narrower contribution is the exact protected target frontier reduction for one storage budget and explicit non replayable outputs under load first execution
The focused comparison and primary sources are maintained in docs/NOVELTY_AUDIT.md

## 3 System model

The captured pipeline is a finite DAG
Each node records an operator and dependencies and parameters and replayability and one content addressed output
Source blobs are mandatory and optional blobs compete for one storage budget
A protected request names historical target nodes
The runtime first loads a node when its blob exists and otherwise replays the operator when replay is declared and every dependency can be produced
It rejects a missing non replayable output and rejects any rebuilt value whose serialization hash differs from the captured identity

The guarantees require complete dependencies and accurate replay declarations and an acyclic graph and a matching execution environment
The current system is an offline planner and does not provide transactional online admission or crash safe replacement of an active store

## 4 Frontier reduction

The live frontier is the union of reverse walks from protected targets
Traversal includes each visited node and continues through its parents only when that node is replayable
An optional blob used only outside this union cannot be loaded or replayed by a protected request
Its physical decision can therefore be removed
Mandatory source decisions are fixed to one and replay decisions forbidden by non replayability or mandatory loading are fixed to zero

The construction uses one reverse traversal and takes O of V plus E time
The full theorem and proof and counterexample conditions appear in docs/FRONTIER_REDUCTION.md

## 5 Implementation

The Python prototype captures block level inputs and preprocessing and fitted state and models and predictions
It deduplicates equal serialized blobs by SHA 256 and records a manifest and source and environment identities
The planner uses SciPy mixed integer optimization and post checks its incumbent against the byte budget and structural coverage and independently recomputed objective
The disk restorer has no access to the original capture archive

Supported estimators currently include logistic regression and random forests and a deterministic scikit learn multilayer perceptron
Opaque external enrichment and entropy backed random augmentation are captured as non replayable outputs

## 6 Experimental method

The evaluation separates capture and planning and restoration measurements
It rotates planner timing order and retains raw trials and request traces and environment details and hashes
Planner V2 uses the full captured model and V3 applies the replayability frontier and V4 also removes fixed variables
Other baselines include full snapshots and mandatory input replay and direct target snapshots and a cost ranked cache

The evaluation contains the earlier storage and concurrency matrices and a repeated Digits and Wine study and an Iris frontier depth study and the new Digits neural study and wide topology study
All reported exact restores recreate captured hashes

## 7 Preliminary results

The Iris frontier study contains 15 histories and 1350 planner executions and 120 exact restores
All 450 matched planner sets reached proven optima and returned equal objectives
At depth 128 V2 used 1256 variables and V4 used 69 which is a 94.5 percent reduction
The median history level planning speedup was 3.38 times with a bootstrap 95 percent interval from 1.24 to 5.32 and V4 was faster in 14 of 15 histories

The wide topology study contains 15 histories and 315 planner executions and 45 exact restores
The largest history has 1038 nodes and 1068 edges
Every solver run was proven optimal and all planner objectives agreed
The median V2 to V4 speedup was 10.47 times and the median variable reduction was 98.21 percent
The largest formulation fell from 7218 variables to 33

The Digits neural study contains six histories and 630 requests across seven policies and five budgets
It uses a one hidden layer multilayer perceptron under deterministic execution and entropy backed random augmentation
V4 restored all 63 admitted requests exactly and blocked 27 requests before execution when their budgets were insufficient
At the 50 percent budget it restored all 18 requests while full snapshots fit zero and full replay restored nine because it could not cross the random boundary
Target snapshots matched V4 coverage on this compact graph and remain an important strong baseline

## 8 Discussion and limitations

The controlled and wide graph results support the exact reduction and show that its benefit increases when large ancestry is hidden behind a mandatory materialization boundary
The neural result shows compatibility with a real fitted neural estimator but it is not a GPU or large model evaluation
The largest topology uses small numerical values and therefore demonstrates planner scaling rather than training throughput

Novelty is provisionally supported by the focused audit but requires backward and forward citation chaining and an independent challenge before submission
The central timing study also needs repetition on a second machine
A PyTorch vision workload and a Transformer workload would improve framework and device coverage

## 9 Conclusion

RecoverML combines explicit replay contracts and content addressed artifacts and storage budget planning and exact restoration
Its replayability frontier removes decisions that no protected load first recovery can reach
The current evidence preserves proven objectives and exact outputs while substantially reducing formulation size on deep and wide graphs
The remaining work is broader framework validation and independent reproduction and final venue specific editing

