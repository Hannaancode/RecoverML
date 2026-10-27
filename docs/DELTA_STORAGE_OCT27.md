# Lossless deltas and storage dependencies, 27 October

The aim is to reduce persistent bytes while preserving every original artifact
hash and the same capability-loss contract. Standard prefix/suffix copying and
the existing lossless codecs provide one additional representation per eligible
artifact. The planner must pay for every delta base. It cannot assume that ML
replay will supply a storage-decoding base.

The [fixed protocol](../configs/delta_storage_oct27.json) includes all 216
previous primary conditions and all 230 frozen transfer conditions. Scientific
pilot results motivated this format; those eight histories are exploratory,
not held-out. Shared tree chunks, joint packing and a base64 transform were
also tried. Their results must remain visible, including unfavorable outcomes.

## Cost model and proof boundary

There are three kinds of artifact in the ephemeral optimization graph:

1. Paid full/delta files, costed by their complete on-disk lengths.
2. Virtual storage-decoded canonical values, derived only from paid files and
   earlier storage-decoded bases.
3. Original ML artifact nodes, reachable from storage-decoded values or from
   their original surviving producers.

Virtual nodes cost one byte more than retaining every full file. Since that
full-file selection is feasible, a certified optimum cannot retain a virtual
node. Projecting the augmented least fixed point onto original artifact hashes
is therefore equivalent to executing the original graph from actually decoded
retained files. Exhaustive small-graph tests include cyclic alternative ML
producers and capability loss. Two independently coded exact formulations must
agree on each claimed encoded optimum.

Optimality is limited to the declared full-file and single-base delta inventory;
it is not optimality over every possible compression or delta encoding. The
original flat format remains an explicit option. Its metadata, roots and files
are counted, so choosing the smaller complete store prevents storage regressions.
The same delta representation is supplied to local search, snapshot selection
and the independent exact oracle. Equal-format oracle ties remain ties.

## Runtime and accounting

Delta files contain their base's original SHA, exact prefix/suffix lengths,
middle length and SHA, and a bounded standard encoded middle. The base order is
acyclic. Missing/corrupt bases, invalid lengths, nested deltas and output-hash
mismatches fail closed. Export of already retained targets requires no ML
imports; replay keeps the original strict environment check. No capture archive
is read during recovery. Storage includes every retained base and all metadata.
Decode work and transient memory may increase; no speedup is asserted.

The broad study is a byte-level transfer, not a new model-replay or latency
experiment. The additional unit/integration tests exercise strict replay across
all four supported census recipe families. A compact adaptive solid archive
of the flat optimum is an explicit stronger byte control. Unavailable Letter
payloads and any solver failure remain in the denominator.

The primary substantial-improvement gate is at least 10% fewer complete-store
bytes in at least 90% of conditions within every primary dataset/recipe/loss
stratum. Passing an overall or selected-subgroup comparison does not pass this
gate. Neither this gate nor any finite benchmark demonstrates universal dominance.
