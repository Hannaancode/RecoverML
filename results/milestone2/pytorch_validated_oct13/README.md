# Final finite-output PyTorch study

This is the final CNN and text Transformer recovery experiment
The earlier diagnostic run is excluded from final neural quality claims

The matrix has 12 captured histories and 216 selections and 432 requests and 834 raw trace events
All 48 admitted V4 requests are exact and 24 budget-infeasible requests are blocked before execution
At 50 percent storage V4 restores 18 of 24 requests and direct targets restore 6
The complete matrix audit passes and no unexpected restoration failures occur

The CNN uses real Digits images and the Transformer uses a balanced 800-document four-category 20 Newsgroups subset per seed
These are small CPU models trained from scratch and the experiment evaluates recovery rather than competitive classifier quality
The final operator rejects nonfinite training loss and weights and predictions

```bash
make pytorch-study
```

Install the CPU PyTorch dependency and prepare the text data as described in the root README first
Every fresh study uses a new folder and the full captures can be regenerated

The companion native-checkpoint folder contains 24 .pt state dictionaries and data provenance and exact round-trip checks
