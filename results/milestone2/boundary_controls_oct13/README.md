# Boundary placement controls

The study compares no boundaries and boundaries on half the branches and a boundary after the shared merge
45 histories and 1215 planner executions preserve every proven objective and 135 exact restores pass
The width is 4 and 16 and 32 and depth is 16 with five seed blocks and nine rotated trials

Median V2 to V4 speedups are 1.00 and 1.91 and 10.13 times respectively
The manuscript uses clustered confidence intervals in paper_evidence_oct13 which resample whole seed blocks across widths
The bootstrap in the original summary is retained as an earlier unclustered derivation and is not used in the paper

These executable small-array controls have deliberately zero replay costs to force the global formulation
They evaluate planner behavior and do not measure neural training or GPU speedup

```bash
make boundary-controls
```
