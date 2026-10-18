# RecoverML full project summary

This is the historical October14 project summary. Later scientific, retinal and Letter experiments and their limitations are recorded in [release status](RELEASE_STATUS_OCT16.md), [final audit](FINAL_SCIENTIFIC_AUDIT.md) and [artifact guide](ARTIFACT_GUIDE.md). The repository manuscript is a dated checkpoint. Original evidence publication is incomplete even though the later raw ledgers are published.

This summary describes the original prototype and the later research work and the final saved paper experiments
The project has working code and automated benchmarks and raw logs and plots and a complete current paper draft
The latest full research artifact is on GitHub and all source and paper and plots and raw evidence files were verified
Paper acceptance and an independent novelty review are separate steps

## 1 The original problem

A machine learning project creates many files while it runs
It creates prepared data and train and test splits and fitted preprocessing state and models and predictions
When we change a model setting we get a new version and after many changes there can be many old versions

Keeping every file makes old versions easy to recover but uses more storage
Deleting every temporary file saves storage but an old output may become impossible to rebuild when an old step cannot run again
Our project studies which files should be kept and which files can safely be rebuilt

The original course idea was fine grained lineage and deterministic time travel for ML pipelines
Lineage means recording where each result came from and time travel means recovering an earlier version
Deterministic means that recovery returns the exact captured result under the recorded execution conditions

## 2 What RecoverML records

RecoverML records the operation and its inputs and settings and output identity and replay rule
These records form a dependency graph
For example a model depends on prepared features and training labels and the predictions depend on that model and test features

A logical node records one operation in one captured workflow
A physical artifact is the actual serialized output stored on disk
Several logical nodes can have identical output bytes and share one physical artifact
RecoverML identifies those bytes with SHA256 and stores shared bytes once

Every loaded file and every rebuilt result is checked against its captured identity
An incorrect result is rejected rather than accepted because it looks close
The captured archive is a validation reference outside the recovery executor and is not a hidden source for missing files

## 3 The first working prototype

We implemented the project in Python and separated capture and graph storage and planning and restoration and benchmarking
We built a command line interface and a runner that can create fresh experiments without overwriting earlier evidence
The early comparisons included saving all outputs and replaying available steps and selecting a smaller store under a byte budget

The original planner was a heuristic and a later planner used an exact mixed integer formulation for the stated load and replay cost model
The budget included required inputs and metadata instead of treating those bytes as free
The planner protected the requested versions and the runtime loaded an available retained output before considering its dependencies

This first objective was to choose a useful retained store within a budget and reduce the estimated recovery work
The later paper objective is different because it minimizes stored bytes while guaranteeing recovery after declared tool losses
Results from those objectives are reported as separate studies

## 4 How planners V2 and V3 and V4 improved

V2 gave the planner a global formulation so several protected versions could share stored artifacts
It also used a guarded shortcut when saving the targets already achieved the estimated lower bound
These were implementation improvements and did not invent the general load versus recompute problem

V3 reduced unnecessary solver work at non replayable boundaries
If the recovery runtime must load an output because its operation cannot replay it does not need to recover that operation's parents along that path
The optimizer can remove artifacts used only behind that boundary while retaining artifacts shared with a live path

V4 kept that reduction and substituted decisions whose values were already fixed
Required inputs have to be saved and a non replayable node cannot have a replay decision
Removing those fixed variables gives the solver a smaller problem while preserving the protected recovery objective under the load first contract

We proved the frontier rule for that contract and checked it with exhaustive small graphs and larger real executable histories
We also tested graphs with no useful boundary and partial boundaries so the speed claim did not depend only on the easiest favorable case

## 5 The main earlier experiments

| Experiment | What we tested | What we measured |
|---|---|---|
| Initial storage prototype | Early retention and exact restoration | The original 6600 request evidence remains in the archive |
| Expanded storage study | More histories and budgets and the V2 planner | 11200 requests across 80 histories and all 1175 admitted V2 requests exact |
| V2 planning comparison | Matched feasible histories | Planning was 19.3 times faster than V1 and planning plus five restores was 3.4 times faster in that study |
| Worker and performance study | Two data sizes and 1 and 2 and 4 workers with repeated trials | All 5400 requests exact with real timestamps and CPU and memory traces |
| New Digits and Wine study | New public data histories and V3 | 3600 requests across 24 histories and all 535 admitted V3 requests exact |
| V3 repeated ablation | The same decisions with and without the frontier reduction | The opaque formulation decreased from 129 to 98 variables and median history planning improved by 1.18 times |
| Iris depth study | Fifteen deeper histories and V4 | A depth 128 formulation decreased from 1256 to 69 variables and median history planning improved by 3.38 times with 120 exact restores |
| CPU neural study | Real Digits data and a multilayer neural classifier | 630 requests with no unexpected failures and 18 of 18 requested outputs recovered by V4 at the 50 percent budget |
| Wide topology study | Graphs with up to 1038 nodes and 1068 edges | All 315 planner runs preserved proven objectives and median variable reduction was 98.21 percent with a 10.47 times median speed improvement over V2 |
| PyTorch image and text study | A CNN on Digits and a Transformer classifier on real 20 Newsgroups text | Twelve histories and 432 requests with all 48 admitted V4 requests exact |
| Native PyTorch checkpoint audit | Separate loading of saved model states | Twenty four native checkpoints and exact prediction checks |
| Placement controls | No boundary and mixed boundaries and a full frontier | Forty five histories and 1215 planner runs and 135 exact restores with median improvements of 1.00 and 1.91 and 10.13 times |

Admitted means that the policy found a valid store within that experiment's budget
The table does not claim that every request at every budget could be admitted
The earlier results and the original milestone paper are preserved

## 6 Why the paper direction changed

The literature review showed that lineage and materialization and checkpointing and replay and exact output identity already have substantial prior work
HELIX studies iterative ML reuse and HYPPO studies equivalent alternative computations and Kishu studies exact notebook time travel
ExoFlow and CHEX and Checkmate also cover related workflow and checkpoint and rematerialization questions

We therefore made the research question more specific
We ask for the smallest shared physical store that protects every required historical output after any loss of at most k declared replay capability groups

A capability group can include several operations and losing that group disables all of them
This models correlated replay call loss instead of treating every operation as an independent failure
The retained files stay intact and the numerical environment must still match capture
This is not a claim of surviving arbitrary file corruption or an uninstalled numerical package

## 7 The current idea through an example

Imagine twelve old model versions that use the same Banknote dataset and much of the same prepared data
We could save twelve models and their prediction arrays as snapshots
We could also save small shared information and rebuild the models when needed

We record two scaling interfaces that independently produce identical captured feature bytes
One is the NumPy scaling path and the other uses the scikit learn transform interface
They are different declared replay calls and are not independent hardware or package failure domains

If at most one declared preprocessing group can be unavailable the planner may keep the split membership and fitted scaler state
If the membership call is unavailable the saved split tells it which rows belonged to the original train and test sets
If one scaling interface is unavailable the other recorded interface can rebuild the exact features
The remaining training and prediction calls can then rebuild the old outputs

In the first measured Banknote split the twelve version snapshot store needs 149616 total bytes
The one loss minimum needs 84916 bytes and all 48 allowed version and outage requests recover exactly
The two loss minimum needs 128732 bytes and all 84 requests recover exactly
Preparing for more possible losses needs more saved information

A rounded CSV export can differ from the lossless feature bytes
We do not treat it as an exact alternative just because the numerical values are close
That control checks that our savings come from verified identities rather than an assumption that every preprocessing path is interchangeable

## 8 How the exact optimizer works

The counterexample engine starts with a small candidate store and asks whether some allowed loss can break a protected output
If it finds a breaking case it adds a necessary storage condition and solves for a new candidate
It repeats until the master proves its minimum and the adversary proves there is no allowed breaking case

The adversary represents a closed set of available artifacts
A closed set contains the output of every available producer whose complete inputs are already in that set
If a closed set contains the saved files but misses a protected target it proves that recovery can fail
Every robust store must retain at least one artifact outside that set and this gives the next storage cut

We prove the adversary equivalence and cut validity and the certified optimum condition
A timeout or an unfinished solve is recorded as unknown and does not become a guarantee

We also implemented an independent exact reference that writes a separate recovery model for every allowed loss set
It uses grounding ranks so a circular alias cannot create data from nothing
Agreement with that independently written formulation checks both the chosen byte minimum and the implementation

## 9 Physical decomposition and the recovery index

The latest optimizer first fixes the mandatory input artifacts and finds components of optional physical artifacts connected by executable producer dependencies
It keeps every shared optional artifact in one component
Splitting only by model version would be wrong when versions share a file

We prove that these components can be solved independently under the same loss bound even when an outage label appears in several components
Every allowed local loss can also occur in a valid global loss set so each component needs its own universal protection
The selected files recombine into a global minimum and the original metadata and required inputs are paid once

For a target with only rooted providers the planner uses an exact count rule
An always available provider or more than k distinct provider groups can survive every allowed k group loss
A producer that requires the missing target itself is not an independent source

The remaining components use the independent scenario engine for at most 64 local scenarios and the closed set engine for larger universes
This cutoff is an engineering choice and not a promise to always choose the faster engine

The recovery index improves another part of the system
It records which producers are waiting for each missing input and updates only those producers when an artifact becomes available
It preserves the old producer ordering and grounding rounds instead of repeatedly scanning every producer
The measured speedup is for certificate construction and must not be presented as the same speedup for loading and rebuilding an entire model

## 10 Final paper experiments

The first corrected tabular paper matrix uses Breast Cancer and Iris and Wine and Banknote with three split seeds and two import formats and twelve versions
It has 24 captured histories and 48 loss bound cases and 28512 real requests across nine policies
RecoverML and the independent exact formulation each restore all 3168 requests and obtain the same proven byte minimum in every case
Mean total storage saving versus target snapshots is 20.26 percent

The larger Digits study uses trained random forests and a neural classifier with hidden layers of 96 and 32 units
It has four histories and eight cases and 1584 requests across nine policies
Both exact engines restore all 176 requests
Forest snapshot savings average 90.63 percent for one preprocessing loss and 81.65 percent for two
Neural savings average 36.36 percent for one and zero for two
The model accuracy readings check that these are real useful trained artifacts and are not claims of improved classification

The neural experiment exposed a model serialization mismatch and the failed diagnostic was preserved
We corrected it with a canonical inference checkpoint and verified exact native inference before capture
The checkpoint preserves inference state and does not claim training optimizer state for resuming fitting

The native DVC study actually adds files to its cache and removes the workspace copies and performs 40 historical version checkouts
Every restored model and prediction file hash matches
Native cache directory and pointer metadata are recorded separately from a common payload and root and manifest total
This measures snapshot storage and checkout and does not measure every possible DVC reproduction feature

The planner scaling study completes 60 runs against an independent analytic minimum
At 24 groups and two losses the original closed set engine has a median of 29.86 milliseconds versus 680.10 milliseconds for expansion
Enumeration is faster in some smaller cases
The index study has 56 timings with identical certificates and reaches a 434.89 times median kernel improvement on the generated depth 2048 chain

The selector validation uses new group counts of 8 and 16 and 32 and widths of 12 and 24 and a new seed
All 108 planner runs match the analytic minimum
The median selector time relative to the faster observed engine is 1.05 and the worst is 2.86 so it is useful but not an oracle

One mixed real graph combines twelve captured branches and 112 protected versions and 264 physical artifacts
The original exact engines agree on both minima and complete 2464 exact disk requests
The one preprocessing loss store needs 1390318 bytes versus 21376829 snapshot bytes and saves 93.50 percent
The two loss store needs 3433246 bytes and saves 83.94 percent
The original global counterexample engine is slower than enumeration on this graph and the paper reports that result

The final component study checks those real minima and twelve new layered AND controls with 10 and 20 and 40 shared loss groups
It completes 118 planning runs and 9288 exact disk requests and agrees with the independent reference or analytic minimum in every case
The controls include producers that need two inputs and failure labels shared across several stages

## 11 Comparison with published methods

The final fresh comparison uses 28 histories and 56 cases and ten policies for 33440 real recovery requests
All main policies receive the same maximum robust byte limit and use the same exact recovery executor

| Method | Exact requests out of 3344 | What we execute |
|---|---:|---|
| RecoverML | 3344 | Final exact physical decomposition and certified local engines |
| HYPPO rank | 2240 | Unchanged pinned released materialization component with our disclosed physical artifact adapter |
| HYPPO frequency | 2291 | Unchanged pinned frequency weighted component with the same adapter |
| Best tested common budget HELIX setting | 1940 | Published streaming rule reimplementation across the declared read speeds and tie orders |

The HYPPO code revision and source hash are pinned and checked
HELIX uses the published decision rule and is not the native HELIX runtime
Its read speeds are 50 and 200 and 800 MiB per second and both orders within an out of scope event are tested
An additional HELIX row receives the larger snapshot budget and is kept separate from the common limit comparison

In the lossless subset all tested main methods recover all 320 no outage requests
Their coverage separates when replay groups are actually disabled
This checks that the advantage is also present when a baseline already works before the outage

The result shows better exact historical recovery coverage for our stated contract at the common byte limits
It does not prove general execution speed dominance over native HELIX or the full HYPPO system on their original future reuse objectives

## 12 The broader outage control

We also add model fitting and prediction to the declared loss groups
The control uses six histories and 36 scope and bound cases and both exact engines agree on every minimum
All 3920 disk requests recover exactly

When model fitting can fail the planner needs to retain the trained models in these workflows
The one loss forest saving falls to about 1.26 percent because the large models can no longer safely be rebuilt
When fitting and prediction can both be lost the same store must survive either loss and it needs every protected model and prediction
Snapshots are then optimal for those captured producer structures even when only one group may fail

This result tells us exactly where the large preprocessing scope savings apply and makes the paper's recovery claim more precise

## 13 Our three contributions

First we define a clear exact historical recovery contract and the smallest shared physical byte store that satisfies it after every allowed correlated tool loss

Second we provide an exact physical component theorem and rooted provider reduction and certified optimization engines and grounded indexed recovery with working code and correctness checks

Third we provide a reproducible study of the price of stronger recovery using published materialization decisions and native snapshot software and real trained artifacts and independent exact references and controls

The proposed novelty is this specific retention problem and its certified physical solution and evidence
Caching and hashes and lineage and generic cuts and alternative computations and generic decomposition already existed and are credited
The review also includes fault tolerant source placement and does not claim that generic placement under failures is new
Independent research review is still needed to challenge the novelty boundary before submission

## 14 Database concepts and hardware

This is an advanced database systems project because it studies provenance and materialized results and shared storage and recovery and cost based optimization
A saved ML intermediate is like a saved query result and replay is like recomputing a query from its dependencies
Historical versions and exact recovery add a time travel and fault tolerance requirement

The main system runs on CPUs and does not require a GPU because it studies artifact retention and recovery rather than faster GPU training
The project includes real neural workloads and earlier CNN and text Transformer evidence
It does not claim frontier scale neural training or large language model performance
Larger model studies can extend the workload scale if the selected venue needs them

The recorded paper host has an Intel Xeon Platinum 8573C processor and an eight CPU quota and an eight GiB memory limit
Numerical libraries use one thread for the paper studies
The final suite has 77 tests with 72 passing and five optional PyTorch checks skipped in the current environment
Earlier PyTorch experiments retain their own source and environment and are not counted as new runs today

## 15 Files and experimental evidence

The repository separates working code and tests and configurations and reports and manuscripts and saved result groups
Earlier submitted evidence remains in results/milestone2 and earlier storage studies remain in results/archive
The current paper evidence is together in results/research/paper_oct14

Raw traces include actual timestamps and exact outcomes and operation events and process work
The original milestone performance study also includes latency percentiles and throughput counters and CPU and resident memory samples
The benchmark runner varies parameters automatically and refuses to overwrite existing evidence
Plots and tables are generated from saved summaries and their input hashes are recorded
Selected stores and exact recorded source versions are archived so reviewers can inspect the files actually needed for recovery

## 16 Current completion and next steps

The working prototype and current experiments and manuscript are complete for internal review
The current paper has a formal problem and six correctness propositions and methods and verified comparisons and plots and discussion and references
The original milestone paper and its evidence are preserved

The final interruption affected an upload and the final additions were restored and the experiments were saved again
The counts in this summary use the final recovered saved run rather than an unsaved earlier capture
The full latest research artifact is on GitHub and the publication receipt records the verified data release

Before paper submission we need a target venue and its required format and an independent novelty review and independent reproduction on another machine
A full native deployment comparison with HELIX or HYPPO would strengthen broader system claims if those are required by the chosen venue
These external steps cannot be replaced by an acceptance guarantee

The project now has a specific research question and three supported contributions and a working exact system and a reproducible body of evidence showing both where it helps and the storage cost of a stronger recovery promise
