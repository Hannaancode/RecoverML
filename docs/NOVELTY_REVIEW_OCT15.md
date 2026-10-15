# RecoverML novelty and significance review

Date: 15 October 2026

Review type: parallel AI review of the current repository and selected primary sources

This is an adversarial research audit and is not an external human peer review. No manuscript text or historical experimental evidence was changed for this review. The associated source register is [literature_sources.json](../results/validation/2026-10-15/scientific_audit/literature_sources.json).

## Finding

The selected literature does not establish a published duplicate of RecoverML's entire stated formulation. It does establish most of its general ingredients and two particularly close algorithmic precedents: deficient-set covering in source placement and implicit weighted hitting-set optimization with a logical oracle.

The defensible candidate distinction is the specific byte-accounted historical ML retention contract with conjunctive replay dependencies and bounded correlated capability losses together with a verified system for that contract. A new application or a combined formulation can be useful but different terminology and a combination of familiar ingredients do not by themselves establish a strong theoretical discovery.

Retain this research direction and narrow the originality claim. Do not describe a weighted master plus counterexample oracle as a newly invented general optimization architecture. No selected-source search can establish 100 percent originality or publication acceptance.

## Tasks 15 to 18

| Task | Status | Completed evidence | Remaining acceptance gap |
|---|---|---|---|
| 15 Fresh systematic novelty review | PARTIAL | Targeted primary-paper review across all named systems plus source placement and implicit hitting sets and selected citation chaining | Exhaustive venue and keyword coverage and complete forward citation chaining were not performed |
| 16 Adversarial novelty matrix | PARTIAL | Named-system objectives and established mechanisms and concrete distinctions are recorded below with primary links | Exact mathematical objective and evaluation details have not been reconstructed for every possible overlapping method |
| 17 Challenge algorithmic originality | PARTIAL | Explicit equivalence to an implicit weighted hitting-set instance and a restricted source-placement connection are derived below | No equivalence or non-equivalence theorem against every prior full published formulation and no independent external challenge |
| 18 Verify scientific significance | PARTIAL | Plausible operational motivation and official service-retirement and model-persistence evidence are identified | No measured natural prevalence of capability loss or exact alternative producers in independent operational histories |

## Repository scope and method

The review examined the current contract and proofs in paper/RecoverML_capability_loss.md and the preceding docs/CAPABILITY_LOSS_NOVELTY.md and docs/NOVELTY_AUDIT.md. It also inspected experiment scope through docs/PAPER_STATUS.md and docs/PAPER_COMPLETION_OCT14.md and selected references to constructed providers and scaler alternatives in src/recoverml/capability_scaling.py and src/recoverml/capability_ops.py.

Primary full papers were opened and relevant sections were inspected. This is a targeted review rather than a claim that every page and implementation of every system received a complete replication audit. DVC was reviewed through its official documentation because it is a software system rather than one fixed research formulation.

Search terms included:

- MEMPHIS holistic lineage reuse memory management and LIMA fine-grained lineage
- CHEX multiversion replay and HYPPO task and artifact equivalence
- Minimum-cost source location with flow requirements and fault tolerance
- Minimum-label cut and correlated edge removal
- Robust materialized-view selection and robust materialization
- Horn theories and directed hypergraph cuts
- Implicit hitting sets and MIP oracle and Benders decomposition
- Retention and replay and capability loss in ML artifacts

Selected citation chains checked were LIMA to MEMPHIS and HELIX to HYPPO and Flor to FlorDB. HYPPO's discussion and references also point to Collab and prior materialization and hypergraph reachability. General source-location and covering literature was followed to deficient-set characterizations. These chains are partial and do not constitute complete forward-citation coverage.

Unfinished search coverage includes full citation-index searches and de-duplication across venues and a detailed follow-up on Collab and newer robust hypergraph-source-placement and robust Horn-abduction formulations. The Gallo et al. institutional record was checked but its complete mathematical paper was not reconstructed during this review. The biochip counterexample-guided checkpoint paper remains prior documented context rather than a new full-paper review in this audit.

## Adversarial named-system matrix

The distinctions below describe what the inspected sources state. Absence of the full RecoverML contract in these selected sources is not proof that no equivalent formulation exists elsewhere.

| Source and exact entry point | Objective and artifact model | Established overlap and assessed boundary |
|---|---|---|
| [HELIX](https://www.vldb.org/pvldb/vol12/p446-xin.pdf) Sections 5.2 to 5.4 and Problem 3 | Execution-cost optimization over workflow DAGs and materialization under a storage limit; the materialization objective includes present materialization time and future execution time | Loading and recomputation and backward slicing are established. It does not state universal bounded capability-loss retention |
| [HYPPO](https://dsachar.net/publication/2024-icde-kss/2024-icde-kss.pdf) Sections III-B and III-C and Problems 1 and 2 | AND/OR directed hypergraphs with fitted operator state and equivalent physical implementations; minimum execution-cost plans and storage-budget materialization for future execution | Alternate producers and preprocessing-state reuse are already close prior art. The stated bounded correlated-loss retention requirement is a distinction in this source |
| [LIMA](https://mboehm7.github.io/resources/sigmod2021a_lima.pdf) Sections 3 and 4 | Instruction-level lineage DAGs and seed capture and deduplicated traces with full and partial reuse | Fine-grained lineage and deterministic reconstruction are established. Its instruction-level granularity is finer than pipeline-step capture. Section 3.4 explicitly discusses result differences caused by execution environment and aggregation order |
| [MEMPHIS](https://openproceedings.org/2025/conf/edbt/paper-82.pdf) Sections 3 to 5 and cache scoring equation 1 | Hierarchical lineage cache across CPU and GPU and Spark with backend-specific eviction and compiler scheduling | Multi-backend tracing and reuse are established. Workload-aware cache and memory management do not state the same persistent historical-retention guarantee |
| [Kishu](https://www.vldb.org/pvldb/vol18/p970-li.pdf) Sections 4 and 5 including the exact-restoration remark | Incremental notebook checkpoints and checkout at co-variable granularity with fallback recomputation | Exact bytestring restoration for supported serializable state is already explicit. Notebook state rollback differs from immutable artifact-retention optimization |
| [CHEX](https://www.vldb.org/pvldb/vol15/p1297-malik.pdf) Section 4 Problem 1 and Section 5 | Minimum-cost complete multiversion replay sequence with a fixed in-memory checkpoint cache; execution-tree representation and traversal heuristics | Historical sharing and multiversion replay are established. Replay-sequence scheduling differs from minimum persistent retention under unavailable producers |
| [ExoFlow](https://www.usenix.org/system/files/osdi23-zhuang.pdf) Section 3.3 Invariant 1 | Annotated distributed tasks and checkpoint vertex cuts protect exactly-once external-output semantics across nondeterminism | Mixed recovery contracts and checkpoint frontiers are established. External side effects and distributed execution differ from immutable artifact bytes |
| [Checkmate](https://proceedings.mlsys.org/paper_files/paper/2020/file/0b816ae8f06f8dd3543dc3d9ef196cab-Paper.pdf) Sections 4.7 and 4.8 | Minimum tensor recomputation cost under a training-memory budget with a time-indexed MILP and implied-constraint simplification | Integer load/recompute optimization and formulation reduction are established. Training activations and lifetimes differ from historical disk artifacts |
| [DVC official cache documentation](https://doc.dvc.org/user-guide/project-structure/internal-files) Structure of the cache directory and Run cache | Content-addressed deduplicated file cache and command/dependency-keyed run cache; the run cache assumes deterministic commands | Identical file contents already occupy one stored copy. Native checkout is a useful snapshot measurement but does not represent all of DVC's pipeline and reproduction capabilities |
| [Disdat](https://www.usenix.org/system/files/opml19papers-yocum.pdf) Sections 2 and 3 | Versioned immutable bundles and contexts for pipeline artifact publication and consumption | Artifact versioning and immutable sharing are established. The inspected paper does not formulate minimum robust retention |
| [FlorDB](https://vldb.org/cidrdb/papers/2025/p33-garcia.pdf) Section 2 | Record/replay and multiversion hindsight logging with adaptive checkpoints and memoization | Historical reconstruction of metadata is established. Recovering retained model/prediction bytes differs from extracting new log expressions retrospectively |
| [FTOpt](https://homes.cs.washington.edu/~magda/papers/upadhyaya-sigmod11.pdf) Section 5.2 objective and Section 6.4 UDO control | Per-operator fault-tolerance strategies optimize expected query time using a failure model; operators can expose limited recovery capabilities | Fault-tolerance-aware physical optimization is established. Worst-case persistent byte retention differs from expected runtime optimization |
| [Minimum-label cut](https://arxiv.org/pdf/1908.11491) problem definition | A selected label removes all graph edges carrying that label | Correlated group removal is an established abstraction. Conjunctive dependencies and selectable retained artifacts are additions in RecoverML's application |
| [Minimum-cost source location](https://www.keisu.t.u-tokyo.ac.jp/data/2007/METR07-39.pdf) Section 2 Lemmas 2.2 and 2.3 | Minimum-cost intact sources satisfy connectivity demands by intersecting every minimal deficient set | Direct overlap with complement closed-set covering. Ordinary graph connectivity is not automatically equivalent to grouped AND-hypergraph closure |
| [Davies and Bacchus](https://www.cs.toronto.edu/~jdavies/daviesSAT13.pdf) Section 2.1 printed pages 4 to 5 | A minimum-weight MIP hitting-set master and logical oracle exchange unmet covering sets until a feasible optimum is found | Direct overlap with the master/oracle/cut architecture and optimality-at-termination argument. It does not establish that the same full ML retention formulation was already studied |

The matrix does not describe these papers as executable benchmark results. No new native executions of these systems were performed for this literature review.

## Explicit implicit-hitting-set equivalence

This derivation is from the current RecoverML contract. It is an equivalence of its optimization structure to an implicit weighted hitting-set instance and is not a claim that a cited paper published precisely the same full formulation.

Let B be the finite physical artifact set and R the mandatory roots and T the protected targets. For each allowed disabled-group set F define

\[
\mathcal A_F=\{A\subseteq B:\ A\text{ is closed under producers available after }F
\text{ and }T\nsubseteq A\}.
\]

Define the implicit set family

\[
\mathcal H=\{B\setminus A:\ F\text{ is allowed and }A\in\mathcal A_F\}.
\]

Then a retained set S containing R is robust if and only if

\[
S\cap H\ne\varnothing\qquad\text{for every }H\in\mathcal H.
\]

Proof in both directions:

1. If S misses a member H = B minus A then S is contained in A. Since A is closed under the surviving producers the least grounded recovery closure of S stays inside A and misses a protected target. S is not robust.
2. If S is not robust choose an allowed F for which its least closure L(S,F) misses a protected target. This least closure belongs to the corresponding family A_F and contains S. Therefore S misses its complement in H.

Thus minimizing the sum of retained byte weights subject to mandatory roots is minimum weighted hitting set over this implicit family. Manifest and capability-contract costs are additive constants. Sets in the implicit family that already intersect R impose no extra optional-retention restriction.

RecoverML's adversary identifies an unhit complement and its master adds the associated covering inequality. This explains the validity of the architecture and its relationship to established implicit hitting sets and logic-based decomposition. It does not make the application useless or establish a complete published-problem duplicate.

The nearest newly identified general algorithm source is Davies and Bacchus Section 2.1. The nearest source-location covering source is Sakashita et al. Section 2. Both should be included in a future manuscript revision when the author resumes drafting.

## Restricted source-placement connection

Restrict every producer to one input and let each loss label disable exactly one producer. Choosing retained artifacts is then choosing intact sources that keep every target reachable after any k edge failures.

For a fixed retained set introduce a super-source with undeletable edges to retained artifacts. Robustness is an edge-connectivity requirement from this source to each target. This is the structure of fault-tolerant source placement. The undeletable edges can be interpreted as capacity greater than the failure budget when expressing the independent-edge-failure restriction through cuts.

Two parts of the full RecoverML model prevent a naive ordinary-graph identification:

- A multi-input producer requires every dependency. Replacing its incoming hyperedge with separate arcs changes AND into OR and admits false derivations
- Removing one shared label can disable several routes together. Edge-disjoint routes alone do not establish robustness under such a label loss

These are concrete modeling distinctions. They leave a narrower open originality question about robust labeled AND-hypergraph source selection rather than about fault-tolerant source selection in general.

## Decomposition and indexed execution

Once roots are fixed and no executable optional dependency crosses components the recovery predicate separates by component. Universal quantification distributes over conjunction:

\[
\forall F\ \bigwedge_i P_i(S_i,F)
\quad\Longleftrightarrow\quad
\bigwedge_i\ \forall F\ P_i(S_i,F).
\]

Any locally relevant failure set of size at most k can occur globally without adding failures elsewhere. Shared labels therefore do not invalidate the decomposition under this bounded-loss contract. Additive optional-byte costs then separate.

This is a useful exact specialization with an implementation burden worth validating. Generic separability after fixing shared variables is established mathematical practice and this review does not certify the decomposition as a new general theorem.

Grounded least closure and cycle rejection follow standard Horn-rule or Datalog reasoning. Dependency counters and an agenda are standard worklist techniques. RecoverML can contribute a verified implementation that preserves its precise wavefront certificate and ordering; indexing alone should not be framed as a new general graph algorithm.

## Operational significance

Capability retirement is a real possible event. Microsoft's official [Personalizer documentation](https://learn.microsoft.com/en-us/previous-versions/azure/ai-services/personalizer/what-is-personalizer) announces service retirement on 25 August 2026. This supports the motivation that an externally controlled replay service can disappear. It does not establish how often this occurs in the evaluated workflows or validate the frequency of their exact alternative producers.

The official [scikit-learn persistence guide](https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations) explains that model loading across scikit-learn versions is unsupported. Recording environment identity is therefore useful. Strict environment refusal demonstrates detection and a safety boundary rather than successful recovery across arbitrary environment changes.

The current local scaler implementations share libraries and machine resources. Their declared capability groups are replay-call restrictions and do not establish independent host or package failure domains. That qualification already appears in the current manuscript and should be preserved.

The operational evidence still needed is:

1. Histories chosen independently of favorable equal-byte producer opportunities
2. Measured occurrence of natural exact alternatives rather than only deliberately paired implementations
3. Declared failure groups linked to genuinely distinct retired interfaces or permission domains
4. A comparison with preserving an executable environment or container when feasible including its storage cost
5. A clear reason the application requires captured bytes rather than prediction equivalence or numerical tolerance
6. Storage versus full restoration cost under a meaningful recovery-delay bound
7. Broader failure domains affecting training and prediction and interpretation of zero-saving cases

More GPU capacity does not resolve these literature or operational-evidence gaps. CPU execution is sufficient for the current formal planner and its checks. A GPU is relevant only for new experiments making broader claims about large neural workloads.

## Defensible contribution categories and decision

A cautious claim is that RecoverML implements a byte-accounted historical ML retention contract over captured physical identities and conjunctive producers with bounded correlated replay loss and supplies exact solving reductions and checked recovery certificates within that model.

Three useful contribution categories are the precise application contract and its relationship to prior optimization problems and the verified specialization of exact optimization and physical graph reductions and the reproducible measurements of when resilience costs extra storage and when sharing helps. These are contribution categories and not three confirmed independent theoretical inventions.

The next evidence with the highest value is a same-contract robustness-aware heuristic comparison and an unseen-workflow study with natural alternatives and measured recovery costs. The current literature review supports further research and a narrower claim but does not support a final strong-publication-readiness verdict. Actual external human review and broader originality checking remain pending.

## Follow-up review after reconstruction on 15 October

This section extends the earlier review rather than treating its unresolved searches as completed. The fresh sources were checked during the reconstruction session and the restored auxiliary experiments are new executions with new receipts. Earlier claims about lost results are not evidence for this follow-up.

### Closer prior work on abduction

[Saikko and Wallner and Jarvisalo, KR 2016](https://www.dbai.tuwien.ac.at/user/wallner/files/SaikkoWJ2016.pdf) was read in full-text form at Sections 3 and 4 and Algorithms 1 and 2. Section 3 gives a generic minimum-cost hitting-set framework with predicate checks and core extraction. Section 4 instantiates it for minimum-cost propositional explanations using SAT reasoning and integer programming. The formal role of our retained artifacts is close to the role of paid hypotheses. This source establishes the general architecture before RecoverML.

[Ignatiev and Morgado and Marques-Silva, ECAI 2016](https://arxiv.org/pdf/1604.08229) was checked at Section 2.2 and Sections 3.2 to 3.3. It revisits AbHS and introduces Hyper through stronger integration of consistency checks and counterexamples. It explicitly treats an unsuccessful entailment check as a source of a set which the next paid explanation must hit. This is another direct reason not to claim that our weighted master and counterexample loop are new general methods.

[Derakhshan et al., SIGMOD 2020](https://www.dfki.de/en/web/research/projects-and-publications/publication/11031) has an institutional abstract describing an Experiment Graph with raw data and intermediate data and models and operations. It reports storage-aware materialization and reuse planning for collaborative ML. The linked full PDF timed out in this session so this extension does not claim a complete theorem-level reconstruction of Collab. The source overlaps with the scientific application and artifact graph and materialization story.

The publisher full text for Kim and Lee and Kim, *Finding a Minimum Source Set in Directed Hypergraphs*, JISE 33(2), 413 to 428 (2017), remains unresolved in this session. Its bibliographic entry and abstract are leads rather than a completed equivalence audit. This unresolved item is not evidence of originality.

### Cost-preserving finite-scenario reduction to weighted Horn abduction

The following is our derivation from the current RecoverML contract. It is not attributed as a theorem published by the sources above and it is not claimed as a new theorem.

Let the allowed failure scenarios be explicitly listed as F and let B be the captured physical artifacts. Introduce one positive hypothesis p_b for each optional artifact b with its retained-byte cost. Zero-byte artifacts can be retained for free first because the recovery property is monotone. Mandatory roots and manifest bytes and contract bytes contribute an additive constant.

For every scenario f and artifact b introduce an availability atom a_(f,b). Build one definite Horn theory with these rules:

1. For every mandatory root r add the fact a_(f,r)
2. For every optional artifact b add p_b implies a_(f,b)
3. For each producer that survives f add the implication from all of its dependency availability atoms to its output availability atom

The hypotheses p_b are shared across all scenario copies. Therefore retaining one physical artifact is charged once even when it supports many versions and many scenarios. The manifestations are all target-availability atoms a_(f,t) for every protected target t and allowed f.

For a selected set S the least model of this positive Horn theory contains exactly the grounded recovery closure in each scenario. This follows by induction on forward-chaining steps: root and retention facts are precisely the initial available artifacts and each producer rule is precisely one legal replay step. Conversely every added availability atom comes from one of those initial facts or a legal replay step. Cycles without a grounded input derive nothing. A positive Horn theory entails a positive atom exactly when that atom belongs to its least model.

Thus S meets RecoverML's complete recovery contract if and only if its selected hypotheses explain all manifestations. The Horn theory is consistent because assigning every atom true satisfies it. The objective is the same paid payload-byte sum plus the same fixed costs. This gives a cost-preserving reduction to weighted positive Horn abduction for an explicit finite scenario list.

The construction has a copy of availability and producer rules for each scenario. It is polynomial in that explicit list and is polynomial in the number of groups for a fixed loss bound k. If k varies with the number of groups the list may be exponential. This derivation does not claim a polynomial compact reduction for arbitrary k or equivalent computational complexity in the compact representation. RecoverML's compact adversary is an implementation choice for avoiding this explicit expansion on suitable cases.

The consequences are direct. AND dependencies and correlated group losses do not by themselves establish a new general explanation-optimization problem because every explicitly enumerated contract can be encoded this way. Any originality claim must identify a more precise application requirement or a validated specialization or a new empirical finding.

### What the new controls establish

The reconstructed [component audit](ABLATIONS_OCT15.md) contains 154 structural planner controls and 110 rows retain exactly the same contract. All tested exact variants agree on optimal bytes. On these four real public-recipe captures removing additional producers changes no optimal payload bytes. Physical deduplication saves only 431 bytes for the Iris capture and zero bytes for the other three. The constructed alternative-producer fixture shows the mechanism can matter but does not show that it is common in real scientific histories.

The separate [annotation sensitivity study](../results/research/scientific_sensitivity_oct15/RESULTS.md) contains 5760 metadata-only controls. It shows that cost and access-weight and eligible-artifact choices can change baseline decisions. It is not a native execution benchmark or an independent sample of 5760 scientific workflows.

The supported contribution categories are stated in [CONTRIBUTIONS_OCT15.md](CONTRIBUTIONS_OCT15.md). Three categories can be presented clearly but three confirmed new theoretical discoveries cannot be claimed from this evidence.
