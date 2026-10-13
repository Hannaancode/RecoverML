# Raw-derived paper evidence

claims.json records the numerical manuscript claims and explicit limits
pytorch_coverage.csv records every policy and budget comparison
model_quality.csv records the fitted classifier quality and architecture size
boundary_control_statistics.csv uses whole-seed block bootstrap confidence intervals
input_hashes.json identifies each raw source and source_hashes.json identifies the analysis implementation and configs

Regenerate into a fresh folder with

```bash
PYTHONPATH=src python -m recoverml.paper_evidence --out results/runs/new_paper_evidence
```
