# Focused novelty audit

Updated 13 October 2026

## Claim being tested

The candidate contribution is not lineage capture or checkpointing by itself
It is an exact reduction for storage budgeted historical recovery in a load first ML artifact graph
The reduction stops backward optimization at declared non replayable outputs and removes decisions that cannot affect a protected recovery

## Search method

The review used primary papers and official publication pages from PVLDB SIGMOD CIDR and USENIX together with arXiv copies when needed
Searches combined ML pipeline lineage materialization time travel recovery replay checkpoint storage budget opaque operation and non deterministic boundary
The audit tests whether a prior system states an equivalent protected target frontier rule with the same feasible recovery set and objective

## Closest systems

| System | Main mechanism | Important overlap | Difference from the candidate claim |
|---|---|---|---|
| HELIX | Chooses load compute and materialization decisions across iterative ML DAGs | Workflow DAG reuse and cost based materialization | Optimizes iterative execution and future reuse and does not state the protected target replayability frontier reduction evaluated here |
| LIMA | Fine grained lineage tracing and reuse inside ML systems | Lineage and eliminating repeated work | Focuses multi level tracing and reuse and cache management rather than storage budgeted exact historical recovery across declared opaque boundaries |
| Kishu | Incremental notebook checkpoint and checkout | Time travel and fallback recomputation | Versions notebook session state at co variable granularity and does not formulate the same artifact retention problem |
| ElasticNotebook | Notebook live migration through dependency aware checkpoint and restoration | Dependency based state reconstruction | Optimizes migration state and not multi version protected target retention under one byte budget |
| ExoFlow | Exactly once DAG recovery with task annotations including nondeterminism | Explicit execution semantics and mixed recovery strategies | Addresses failure recovery in distributed workflows and not offline selection of artifacts for many historical targets |
| FlorDB | Incremental metadata and hindsight logging across ML development | ML lifecycle provenance versions and checkpoints | Focuses metadata capture and querying rather than the frontier optimization theorem |
| Disdat | Immutable versioned bundles for ML pipeline artifacts | Artifact versioning and reproduction | Provides artifact management abstractions without the tested global planner reduction |
| Materialization and Reuse Optimizations | Reuses common operators across production data science pipelines | Shared subgraphs and materialization | Optimizes concurrent or production pipeline execution rather than exact time travel across mixed replay contracts |
| CAPS | Cost aware selection of AutoML pipelines represented as a hypergraph | Constrained optimization over pipeline structure | Selects which candidate pipelines to execute and does not select historical recovery artifacts |
| Checkmate | MILP based tensor rematerialization under a device memory budget | Budgeted load and recompute planning and formulation simplification | Schedules in-training tensor lifetimes rather than immutable disk artifacts protected across historical requests |

## Primary sources

1. Xin et al. HELIX Holistic Optimization for Accelerating Iterative Machine Learning PVLDB 2018 https://www.vldb.org/pvldb/vol12/p446-xin.pdf
2. Phani et al. LIMA Fine grained Lineage Tracing and Reuse in Machine Learning Systems SIGMOD 2021 https://doi.org/10.1145/3448016.3452788
3. Li et al. Kishu Time Traveling for Computational Notebooks PVLDB 2025 https://www.vldb.org/pvldb/vol18/p970-li.pdf
4. Li et al. ElasticNotebook Enabling Live Migration for Computational Notebooks PVLDB 2024 https://www.vldb.org/pvldb/vol17/p119-li.pdf
5. Zhuang et al. ExoFlow A Universal Workflow System for Exactly Once DAGs OSDI 2023 https://www.usenix.org/conference/osdi23/presentation/zhuang
6. Garcia et al. Flow with FlorDB Incremental Context Maintenance for the Machine Learning Lifecycle CIDR 2025 https://vldb.org/cidrdb/papers/2025/p33-garcia.pdf
7. Yocum et al. Disdat Bundle Data Management for Machine Learning Pipelines USENIX OpML 2019 https://www.usenix.org/conference/opml19/presentation/yocum
8. Boehm et al. Materialization and Reuse Optimizations for Production Data Science Pipelines https://www.dfki.de/web/forschung/projekte-publikationen/publikation/12706
9. Kontaxakis et al. CAPS Cost Aware ML Pipeline Selection PVLDB 2026 https://www.vldb.org/pvldb/vol19/p1427-kontaxakis.pdf
10. Jain et al. Checkmate Breaking the Memory Wall with Optimal Tensor Rematerialization MLSys 2020 https://proceedings.mlsys.org/paper_files/paper/2020/file/0b816ae8f06f8dd3543dc3d9ef196cab-Paper.pdf

## Adversarial recheck on 13 October

HELIX Section 5.4 explicitly traverses backward from outputs and prunes unvisited nodes and its execution model uses load compute and prune states
The HELIX 2018 demonstration also states that loading a node can prune its ancestors while shared descendants may still require some of them
This means that backward slicing and stopping computation at a materialized result cannot be presented as a new general idea
Primary demonstration https://www.vldb.org/pvldb/vol11/p1958-xin.pdf Section 2.2

ExoFlow Section 2 discusses saved task frontiers and committing nondeterministic outputs and Section 3.3 formalizes a checkpoint vertex cut
This means mixed deterministic and nondeterministic recovery contracts and the term frontier are also established
Primary paper https://www.usenix.org/system/files/osdi23-zhuang.pdf Sections 2 and 3.3

Kishu Section 5 states exact bytestring restoration for serializable co variables and describes its nondeterministic fallback boundary
Therefore exact restoration and serialization identity also cannot be presented as unique to RecoverML

Checkmate Section 4.7 uses a constrained MILP and Section 4.8 removes constraints implied by optimality
Thus mixed integer budget optimization and model simplification need explicit attribution

## Finding

The reviewed systems establish that lineage materialization reuse checkpointing and time travel are not new
The remaining candidate distinction is an explicitly proved physical-blob-aware presolve for one byte budget protecting multiple historical requests under a fixed load first execution contract
The experiments test physical aliases and shared live ancestry and objective preservation and include no boundary and partial boundary controls
The review has not located this identical formulation in the selected sources but different problem wording does not by itself establish an inventive algorithm
The novelty strength is therefore modest and provisional and the paper should emphasize the checked formulation and empirical boundary conditions rather than claiming a new general checkpoint frontier principle

This is not proof that no equivalent result exists
Before submission the search must be repeated with citation chaining and author terminology and a second reviewer should challenge the matrix
The paper must therefore say that RecoverML introduces the reduction within its declared model and must not claim that it invented lineage checkpointing or workflow reuse

