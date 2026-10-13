# Native checkpoint evidence

24 native .pt state dictionaries round-trip with exact canonical weight identity and exact prediction identity
All final probabilities and weights are finite
The loader runs with map_location CPU and weights_only enabled

checkpoint_verification.csv links each file hash to its original canonical artifact identity and parameter count and test accuracy
dataset_provenance.json records source indexes and data hashes and training-only vocabulary and preprocessing
HASHES.json records the exported evidence file identities

The files support inference from trained weights and do not represent optimizer state or training resume
Native container byte hashes check integrity and the canonical numerical hash defines the restoration identity
