# Exact ML recovery when replay tools become unavailable

## The idea in simple words

RecoverML now chooses what to save before a replay tool becomes unavailable and protects several old model versions with one shared store
It keeps enough files to recover every protected model and prediction after any allowed combination of tool outages and checks the recovered bytes against their original hashes

For example two recorded scaler implementations can produce the same feature bytes and one can rebuild the features when the other is unavailable
Keeping the small fitted scaler state can then be cheaper than keeping the full feature table or every model checkpoint
The planner also prepares for losing the tool that made the scaler state and therefore it saves that state when needed
When both scaler implementations may become unavailable the planner chooses a larger store

Our specific proposed novelty is **minimum byte retention for exact historical ML recovery under bounded loss of correlated replay capabilities using counterexample guided closed set storage cuts**
This is an implemented and tested research contribution candidate and publication originality still needs independent review against the closest work

## Three contributions

1. **A recovery contract that plans for tool outages**
   One physical store protects all requested historical models and predictions after any loss of at most k declared tool groups and counts source data and metadata as part of storage
   Several replay steps can belong to the same group so a single outage can disable them together

2. **A planner that learns what must be saved from failing cases**
   A solver looks for an allowed outage that would break recovery and returns a set of unavailable outputs
   The planner turns that failure into a necessary storage rule and repeats until it has a solver certified minimum store that survives every allowed outage
   Captured equal byte producers give extra recovery paths and closed sets handle cycles without treating a cycle as a source of data

3. **Measured storage savings with exact recovery and clear controls**
   The evaluation combines four public datasets and genuinely executed scaler implementations with outage injection and independent small graph checks
   It measures the storage cost of stronger outage protection and includes rounded data and short histories where extra paths give less benefit
   Raw request traces and selected stores and planner certificates make the results inspectable and reproducible

## Closest literature and the boundary of the claim

These comparisons come from primary sources and distinguish the published objective from our proposed recovery contract
They do not establish that no other paper has studied the full combination

| Prior work | Existing idea we credit | Specific distinction investigated here |
|---|---|---|
| Kontaxakis et al. HYPPO ICDE 2024 | Equivalent tasks and artifacts and alternative hypergraph paths and storage budget materialization for cheaper pipeline execution | We minimize a shared physical byte store subject to exact recovery of historical targets for every allowed capability loss set |
| Shayan et al. TCAD 2020 | A solver finds counterexamples and checkpoint placement is updated until the defense is secure | We generate necessary storage inequalities and solve a global byte objective for artifact recovery rather than placing monitoring times for a biochip |
| Gallo et al. Mathematical Programming 1998 | Horn satisfiability and directed hypergraph cuts and integer formulations | Our oracle applies closed sets to physical artifact identities with correlated replay loss and derives complement cuts for the retention master |
| Zhang and Tang 2019 | Removing a label removes all edges that carry that label | We use tool groups for correlated producer loss and combine them with shared byte retention and multi input replay dependencies |
| Upadhyaya et al. FTOpt SIGMOD 2011 | Choosing fault tolerance strategies for parallel queries to reduce expected processing time under failures | Our objective is stored bytes and our constraint is recovery for every bounded declared loss set |

Equivalent outputs alone are not our novelty and counterexample guided checkpointing alone is not our novelty
The older Nix and provenance storage work discussed in the preceding research notes remains relevant
We have not run HYPPO or FTOpt as executable baselines and do not claim performance superiority over them

Primary sources

- HYPPO DOI [10.1109/ICDE60146.2024.00024](https://doi.org/10.1109/ICDE60146.2024.00024) and [author page](https://dsachar.net/publication/2024-icde-kss/) and [institutional full paper](https://upcommons.upc.edu/server/api/core/bitstreams/ab9906b1-3da1-4b53-8d61-2d3c26dd2a01/content)
- Shayan et al. DOI [10.1109/TCAD.2020.2988351](https://doi.org/10.1109/TCAD.2020.2988351) and [primary full paper](https://www.cda.cit.tum.de/files/eda/2020_tcad_how_secure_are_checkpoint-based_defenses_in_digital_microfluidic_biochips.pdf)
- Gallo et al. DOI [10.1007/BF01581727](https://doi.org/10.1007/BF01581727) and [institutional record](https://iris.unimore.it/handle/11380/585403)
- Zhang and Tang [arXiv:1908.11491](https://arxiv.org/abs/1908.11491)
- FTOpt DOI [10.1145/1989323.1989350](https://doi.org/10.1145/1989323.1989350) and [authors' project page](https://nuage.cs.washington.edu/projects.php/pubs/benchmark/astro-nbody/people.php)
- Banknote data by Volker Lohweg [UCI record](https://archive.ics.uci.edu/dataset/267/banknote+authentication) and DOI [10.24432/C55P57](https://doi.org/10.24432/C55P57) under CC BY 4.0

The HYPPO full paper and the biochip checkpoint algorithm were read rather than relying on search summaries
The FTOpt comparison uses its published objective and does not infer every detail of its implementation

## Formal contract and why the planner works

Let B be the physical artifacts identified by captured hashes and R the mandatory retained roots and T the protected model and prediction artifacts
Each replayable producer p has dependency artifacts D(p) and output o(p) and optionally one capability group c(p)
The graph retains logical provenance while storage and reachability use physical identities

For a retained set S and disabled group set F let L(S,F) be the least closure starting from S and applying all available producers whose complete dependencies are present
We solve

\[
\min_{R\subseteq S\subseteq B}\left(M+C+\sum_{b\in S}s_b\right)
\quad\text{subject to}\quad
T\subseteq L(S,F)\ \text{for every }F\text{ with }|F|\le k
\]

M is the original manifest size and C is the capability contract size and neither is omitted from the reported byte totals
All compared policies use the same captured graph and root requirement and contract

The storage master has one binary variable x_b per physical artifact and fixes roots to retained
The adversary has membership variables y_b for a candidate closed set A and failure variables f_c for capability groups
It requires S to be inside A and at least one target to be outside A and at most k groups to be disabled
For each grouped producer it enforces

\[
y_{o(p)}-\sum_{d\in D(p)}y_d+f_{c(p)}\ge1-|D(p)|
\]

The f term is omitted for an ungrouped producer
Dependency blob identities are unique within this constraint and repeated output identities accumulate coefficients correctly
The objective first minimizes the number of losses and then maximizes the closed set size to obtain a smaller complement cut

**Oracle equivalence**
If the least closure misses a target it is itself a feasible closed set for the adversary
If any closed set contains S and misses a target then the least closure is contained in that set and therefore also misses the target
This argument applies to cycles because closure starts with retained values and never creates a value merely from a cycle

**Valid storage cut**
For a counterexample closed set A under F every robust store S' must contain an artifact outside A
Otherwise S' is contained in A and its recovery closure under the same F remains in A and misses the target
Thus the inequality sum of x_b over B minus A is at least one and is necessary for every robust store
The implementation independently checks the returned closed set and a grounded recovery certificate before adding the cut

**Optimality at certified termination**
All master cuts are necessary so every proven master optimum is a lower bound on robust storage
When the adversary proves that no bounded loss can break the current store that store is feasible and meets the lower bound
Its byte optimum is therefore certified within the encoded model and solver tolerances
Timeouts and iteration limits return an unknown result and never a robustness or optimality claim

The master uses storage variables only and the separation oracle uses artifact membership and group loss variables
Neither expands replay variables once per failure scenario nor needs topological rank variables

## What was executed

| Study | Captured histories and planning cases | Robust exact recoveries | Storage result |
|---|---|---:|---|
| Three version pilot | Six histories and twelve k specific cases on Breast Cancer and Iris and Wine | 198/198 | Zero savings over full target snapshots |
| Twelve version standard study | Twelve histories and twenty four cases on the same three datasets | 1584/1584 | 15.52% mean savings over full target snapshots |
| New Banknote study with one local scaler backend | Six histories and twelve cases with three split seeds | 792/792 | 14.02% mean savings over full target snapshots |
| Banknote with two scaler backends | Six histories and twelve cases with three split seeds and four policies | 792/792 | Benefit depends on the format and the outage bound as shown below |
| Generated scaling controls | Six graphs with 16 or 48 or 96 tool groups and k of 2 or 3 | 99 exact version probes and 528 exact target probes | All storage optima match independent analytic minima |

The combined standard and single backend Banknote studies contain 36 planning cases across 18 captured histories and their robust and snapshot policies each recover 2376/2376 requests
The nominal minimum store recovers 1068/2376 requests and the robust store averages 15.02% fewer total bytes than full target snapshots
These are descriptive averages over the constructed cases and not population estimates
The twelve historical versions and the multiple outage scenarios share captured data and are not independent dataset samples

In the dual backend experiment the NumPy scaler and the scikit learn transform execute separately and exact packed feature hashes are checked
Scaler fitting and the scikit learn transform share one correlated capability group while NumPy scaling and membership generation are separate groups
The extra baseline is the exact minimum store when all declared groups are unavailable and is evaluated under the same bounded loss requests

| Dual backend Banknote condition | Saving against full target snapshots | Saving against the all groups unavailable minimum store | Exact robust requests |
|---|---:|---:|---:|
| Lossless NumPy import and at most one group loss | 43.24% | 34.04% | 144/144 |
| Lossless NumPy import and at most two group losses | 13.96% | 0% | 252/252 |
| Rounded six digit CSV and at most one group loss | 13.96% | 0% | 144/144 |
| Rounded six digit CSV and at most two group losses | 13.96% | 0% | 252/252 |

For seed zero in the first condition the robust store is 84917 bytes and full target snapshots use 149617 bytes and the conservative minimum store uses 128733 bytes
The small fitted state and membership checkpoint keep the remaining scaler usable after one outage
With two outages both scaler paths can disappear so the planner selects a larger retained set
The rounded CSV output does not have the exact local feature identity so the cheaper alternative cannot be substituted

The dual backend study records 3168 attempts across four policies and 2772 exact recoveries and 396 expected blocked nominal requests
The robust and snapshots and all groups unavailable policies each recover all 792 requests while the nominal store recovers 396/792

An independent audit extracts the saved selected store archive and repeats all 3168 request outcomes with no capture archive available
It reproduces all 2772 exact requests and all 396 expected blocked requests and keeps environment and implementation verification enabled

The largest generated case represents 147537 allowed loss combinations and uses five adversary calls and four cuts
All tool groups occur in protected derivations and are not irrelevant padding
Coverage of the full universe comes from symbolic certification and an analytic family argument and selected disk probes were executed
We did not execute all 147537 scenarios and the generated providers are local simulated capability labels rather than remote services

## Scope and reproducibility

Outages are injected restrictions on particular replay calls and do not uninstall NumPy or scikit learn
Training and prediction and file decoding remain available and retained files remain intact and the numerical environment must match capture
The capability map is trusted and the declared surviving replay recipes must remain valid and deterministic
Exact recovery refers to artifact bytes and does not reproduce historical wall clock events
This study measures storage and recoverability and does not claim better classification accuracy or a latency speedup
The earlier neural studies remain preserved and this new study does not establish the same gains on large neural networks

The full suite completed 63 tests with 58 passing and five optional PyTorch tests skipped in the current environment
New planner checks include 24 generated logical graphs and all storage subsets and all bounded failures through an independent recursive path oracle and budget infeasibility one byte below the optimum
Other checks cover correlated losses and alias cycles and actual disk recovery through a surviving backend and extension hash rejection

```bash
make test
make capability-study
make capability-banknote
make capability-dual-banknote
make capability-scaling
```

Each experiment refuses an existing destination and therefore create a new run path when repeating it
The local source checkpoints are f625a6f for the initial single backend study and d19595c for the dual backend study
Exact initial source copies are also saved under source_snapshot and the current tracked source matches the complete dual study provenance
The Banknote only intermediate source and dual pilot intermediate source are preserved with matching recorded hashes under the evidence source_snapshot folder
The current dual study is the complete four policy run and its pilot report predates the additional all groups unavailable summary fields

Saved evidence is in [results/research/capability_loss_oct13](../results/research/capability_loss_oct13/README.md)
That folder includes the pilot and all controls and raw compressed JSON and complete selected stores and source provenance and the completed test log
The script scripts/capability_disk_audit.py reproduces the archived dual study outcomes without recapture
The current paper and milestone results remain the earlier checkpoint and these new claims are documented separately for the next paper revision

## Next paper work

Run the closest relevant baseline implementations or clearly identify an objective mismatch and provide a justified comparable adaptation
Collect independent real workflow histories with actual retired replay interfaces and measured exact alternative frequency
Extend this capability contract to larger trained neural artifacts and independently reproduce the byte and recovery results on another environment
Have an independent reviewer challenge the formal distinction and proof and then revise the paper around claims that survive that review
