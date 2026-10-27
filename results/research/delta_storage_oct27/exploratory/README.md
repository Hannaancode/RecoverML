# Exploratory local pilots, 27 October

These are exploratory measurements on the previously published **eight
scientific histories** (48 conditions), not a held-out experiment. They informed
the delta format and the subsequently fixed 446-condition evaluation. They are
not new model replay, speed measurements, or a claim of universal superiority.

The input is the original scientific block from the October 26 encoded-storage
release, with its saved adaptive encoded objects and canonical hashes. The
scripts decode and verify the original payloads before analysis. The scripts
refer to its local materialization at
`work/encoded_all_originals/transfer/scientific`.

- `pilot_shared_oct27.*`: all 48 conditions and both the flat-optimum and snapshot
  selections (96 rows). Compares exploratory tree-marker chunks, joint adaptive
  packing and a conventional USTAR/XZ6 container. Chunk metadata is included in
  its size estimate. This is a representation pilot, not an implemented shared
  chunk recovery system or a new optimum. Joint packing and the XZ control
  often outperform these chunks; the failures are retained.
- `pilot_structured_oct27.*`: replaces sufficiently long canonical-model base64
  strings with framed, byte-shuffled binary segments before existing compression.
  Many files become larger. This was rejected and is **not** implemented as a
  production format. The pilot measures encoding size, not an independently
  verified inverse transform.
- `pilot_delta_oct27.json`, `pilot_delta_oct27.py` and
  `pilot_delta_oct27_v2.log`: deterministic longest-prefix/suffix candidate
  investigation, including the existing full-file cost. Its provisional delta
  count includes only 16 framing bytes; **it is not a complete-store result**.
  The production implementation instead pays its full 89-byte header, required
  base files and all metadata. Only the subsequent audited experiment supports
  complete-store claims.
- `pilot_delta_oct27.log`: preserved **partial, interrupted** first attempt,
  which compressed each possible model-base pairing. It was stopped to avoid
  repeatedly compressing large, mostly unrelated models. The completed v2
  chooses the maximum-overlap base before compression. The final `.py` is v2;
  no exact source snapshot of the aborted version is asserted.

These local pilots were not captured by a source-pinned cloud runner. Their
source files, data and logs are preserved verbatim with an inventory of hashes.
The original standard encoding functions came from the preceding released
implementation; no claim is made that this pilot directory alone recreates
the entire local execution environment. Treat its figures as exploratory.
