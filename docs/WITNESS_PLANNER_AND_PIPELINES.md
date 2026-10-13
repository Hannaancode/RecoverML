# Joint artifact witness planner and full pipeline tests

This extends the separate research branch and leaves the main paper and earlier results unchanged

## What changed

The first witness experiment searched every possible retained set
That works only for small graphs
The new optimizer selects retained physical files and valid producers together with a mixed integer model
It protects every requested version and includes the cost of the manifest and required source data

The objective is minimum storage for complete recovery
This differs from the earlier V2 to V4 objective which minimizes modeled recovery work within a storage budget
Therefore these are new storage experiments and not a claim that the existing latency planner became faster

## Matching baseline

The logical baseline uses the same storage objective and the same manifest and mandatory inputs
It follows original parents and it loads any retained artifact first
The witness variant may use another captured producer with the same output hash
Each policy is solved to a proved optimum in the reported runs
The replay executor rebuilds its certificate independently of the solver choices

## Model and proof sketch

Each physical blob has a binary retained variable x
Each replayable producer has a binary selected variable r
For witness recovery the active value for a blob is x plus the sum of its selected producers
An active value is at most one and each target value must be active
Every selected producer requires active input blobs
All mandatory roots must be retained

Each blob also has a bounded rank
Every selected producer requires its output rank to exceed each input rank by at least one
This prevents an alias cycle from supplying its own starting value
The objective is the sum of retained physical byte sizes and fixed metadata
An optional budget constraint rejects a minimum that does not fit

A feasible solution defines a finite grounded dependency order
Following the order from retained values gives a valid recovery certificate under the declared pure replay contracts
Conversely any finite valid recovery certificate can be reduced to one producer per physical value and assigned topological ranks
Therefore the integer model and the grounded recovery semantics have the same feasible retained sets
Continuous ranks suffice since strict increase already rules out a directed cycle
Hash checks during actual recovery remain required

The logical variant has an active variable per original node and a load variable tied to its physical retained variable
It uses the same rank rule on original dependencies and prohibits replay of a retained value

This uses standard optimization and acyclicity techniques and is not claimed as a new MILP technique

## Independent validation

32 generated logical graphs are checked against an independently written recursive path oracle and all possible optional physical subsets
Both planners match the exact minimum byte count
The alternative planner rejects a budget one byte below the optimum
Explicit alias cycle and empty graph controls are included

## Full prediction pipelines

The public Breast Cancer and Iris and Wine datasets use five split seeds and three model versions
StandardScaler fitted only on training rows prepares features
A legacy preprocessing branch exports and imports a serialized feature array
A separate local analysis branch records its fitted scaler and standardization recipe
The legacy import is declared unavailable for replay after capture

The formats are NumPy and CSV with 17 significant digits and CSV with 6 significant digits
The serialized bytes are round tripped through the real format readers and writers in memory
Output equality is discovered by hashing and is not copied or forced
The recovery stores and all model and prediction recoveries use actual files on disk

Each request protects the trained logistic model and its prediction array
No intermediate feature is added as a target to force a storage saving
Both minimum storage policies can instead choose to save model or prediction files

There are 45 histories and 270 exact version recoveries across both policies
Thirty histories have a discovered lossless feature witness and fifteen rounded CSV histories do not
For the lossless cases mean total storage savings are 17.86 percent including mandatory source data and metadata
The new executor restores 90 of 90 versions at its smaller minimum storage and the old executor restores zero of 90 at that same storage
The rounded CSV control saves zero bytes and both executors recover all 45 versions at their shared minimum

This is a constructed legacy producer availability experiment on real data
It is not an independently collected production pipeline dataset and does not measure how frequently legacy producers disappear
Five split seeds are variations within each dataset and not five independent datasets
Recorded recovery times are descriptive and no latency speedup is claimed
Extra computation may be needed to achieve the storage saving

## Scaling with physical alias cycles

The generated family includes an opaque target and an identity producer for each target
The identity producer creates a physical self loop and cannot start recovery
Zero and half and all targets have a separately grounded direct producer
Unwitnessed opaque targets must be stored and witnessed targets need only mandatory roots
This provides an analytic minimum independent of the planner

The first matrix has 27 cases and 81 version recoveries and 1512 exact target recoveries with up to 385 logical nodes
Both planners match their respective analytic storage lower bounds in every case
These are deliberately generated controls and are not natural duplication evidence
An additional large run has three cases with up to 3073 logical nodes and nine version recoveries and 3072 exact target recoveries
The large run also matches the analytic lower bounds for both policies in all cases

## Closest prior work and revised novelty boundary

Nix content addressed builds already map distinct derivations to equal output identities
The Nix RFC describes resolving differing upstream derivations through equal content addressed outputs
Dolstra chapter 6 already discusses multiple derivations that can produce the same content and selection among paths
Therefore output identity across different producer lineages is not an invention of this project

Sources
https://github.com/NixOS/rfcs/blob/master/rfcs/0062-content-addressed-paths.md
https://nixos.org/~eelco/pubs/phd-thesis.pdf

Adams and colleagues in HotCloud 2009 already describe using provenance and deterministic recomputation instead of storing outputs and keeping result hashes to verify reconstruction
Knockoff in 2017 already investigates retaining nondeterministic inputs and reconstructing historical files to reduce cloud storage
Therefore preserving exact historical data through storage and recomputation is also not a new general idea

Sources
https://www.usenix.org/legacy/event/hotcloud09/tech/full_papers/adams/adams_html/index.html
https://www.usenix.org/publications/login/fall2017/dou

The remaining candidate is a carefully scoped ML artifact recovery system combining captured byte equality and unavailable original producers and shared storage selection for protected histories and independent grounded certificates
This is implemented and measured but its publication level novelty is not established
An independent real workflow collection and comparisons with closely related implementations remain important

## Reproduce

```bash
PYTHONPATH=src python -m unittest discover -s tests -p test_witness_optimizer.py -v
PYTHONPATH=src python -m recoverml.witness_pipeline --output results/runs/new_witness_pipeline --seeds 5 --versions 3
PYTHONPATH=src python -m recoverml.witness_scaling --output results/runs/new_witness_scaling --widths 8 32 128 --seeds 3
PYTHONPATH=src python -m recoverml.witness_scaling --output results/runs/new_witness_scaling_large --widths 1024 --seeds 1
```

Evidence is stored in results/research/witness_pipeline_oct13 and results/research/witness_scaling_oct13 and results/research/witness_scaling_large_oct13
Earlier experiments remain available without being replaced
