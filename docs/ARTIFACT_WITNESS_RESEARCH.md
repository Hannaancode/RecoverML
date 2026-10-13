# Verified alternative recovery experiment

The existing V2 to V4 results and the paper remain unchanged

## Idea in simple words

An outside service can produce a feature file and we may not be able to run that service again
But another saved pipeline step may have produced the exact same file
Therefore we can run that other step and check every byte before using the file
We recover the file and we keep the original record of how it was first made

This experimental feature is separate from the current recovery rules
It never claims that an outside event was repeated
It never reads the capture archive during recovery

## Candidate contribution

The candidate is a byte verified alternative producer certificate for artifact recovery across captured ML histories with non replayable operations
It extends recoverability beyond a fixed logical parent path while retaining original provenance
Hash equality identifies captured values and is not a general proof that two programs are equivalent

This is a working research candidate and not an established first invention

## What was measured

Two new datasets are Breast Cancer with 569 rows and 30 columns and Diabetes with 442 rows and 10 columns
Ten shuffled histories per dataset each contain three feature outputs
The three conditions are an exact alternative and a changed alternative and no alternative
The alternatives are deliberately created for this mechanism test
The shuffled histories are not independent new datasets

Both policies use the same manifest and mandatory inputs
All optional physical subsets are enumerated to find the minimum storage for full coverage under each recovery rule
This exhaustive experiment is small and does not establish a scalable joint optimizer

There are 60 cases and 360 exact disk recoveries across the two policies
In the 20 exact alternative cases the mean reduction in total stored bytes including metadata is 73.63 percent
At the witness policy minimum budget it restores 60 of 60 requested versions and the existing logical executor restores zero of 60
The changed and absent controls save zero bytes and both policies recover 60 of 60 at their shared minimum budget in each condition

These are feature artifact storage results and not model accuracy improvements or neural training speedups

## Grounding and proof sketch

Let A0 be the retained physical blobs
At round k plus one add the output of each declared pure deterministic captured producer whose input blobs all belong to Ak
Stop when no output is added

Soundness follows by induction on rounds
The initial values are verified retained bytes and every later value is produced from earlier verified values and is checked against its captured hash
Completeness holds for finite producer derivations under the declared contracts
Induction on derivation height shows that each reachable output enters a round
Any output reachable under the old logical rule is also reachable under this rule

Equal values can turn an acyclic logical graph into a cyclic physical graph
The rounds prevent a cycle from providing its own missing starting value
This is standard least fixed point reasoning and is not claimed as a new mathematical technique

Five regression tests cover exact alternative recovery and a self supporting cycle and corrupt storage and a wrong replay contract and an independent path enumeration oracle on 64 generated graphs and all their storage subsets

## Evidence against a broad claim

An audit of all 12 existing validated neural manifests found no non replayable blob derivable from roots through an alternative
Therefore this experiment does not improve the earlier neural results
It demonstrates a conditional extension and the natural frequency of useful witnesses remains unproven

## Critical literature check

LIMA already implements fine grained ML lineage and reuse and reconstruction
Its lineage equivalence compares opcode and data item and recursively equivalent inputs
The investigated distinction here is equality of captured output bytes across different producer lineages and rebuilding an artifact behind a non replayable original event
This distinction must still be checked against its full implementation and other systems

Source: Phani and Rath and Boehm 2021 LIMA
https://mboehm7.github.io/resources/sigmod2021a_lima.pdf

E graph extraction already selects equivalent computation paths and explicitly handles cyclic alternatives
Therefore alternative path selection and acyclic extraction cannot be presented as new ideas

Source: He and Dong and Malik and Gupta 2023 Improving Term Extraction with Acyclic Constraints
https://pldi23.sigplan.org/details/egraphs-2023-papers/3/Improving-Term-Extraction-with-Acyclic-Constraints

## Next gate for a publishable contribution

Measure naturally occurring alternative witnesses in real imported feature pipelines and cached historical outputs
Compare with lineage reuse and ordinary retained blob deduplication
Add a storage budget optimizer for many physical alternative producers and validate it with an independent exhaustive oracle
Measure certificate size and planning overhead and actual recovery latency
Ask an independent reviewer to challenge the novelty and the artifact versus event distinction

## Run it

```bash
PYTHONPATH=src python -m unittest discover -s tests -p test_witness.py -v
PYTHONPATH=src python -m recoverml.witness_experiment --output results/runs/witness_candidate_new_run
PYTHONPATH=src python -m recoverml.witness_audit --source results/milestone2/pytorch_validated_oct13/capture_archives --output results/runs/new_neural_witness_audit.json
```

Published summaries and raw execution traces are in results/research/artifact_witness_oct13
Full local stores are reproducible experiment outputs and are kept outside the published evidence snapshot
