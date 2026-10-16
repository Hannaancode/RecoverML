# Fresh cloud reproduction on 15 October 2026

A fresh clone on a separate GitHub hosted Azure Ubuntu machine completed the
compact scientific protocol at commit `c6d26a014133fc1cf52951af81c2bafec9a5ee6b`.
The complete workflow succeeded and its three jobs passed.

[Workflow run and downloadable artifacts](https://github.com/Hannaancode/RecoverML/actions/runs/38773600816)

The machine recorded Ubuntu 24.04.5 and four virtual CPUs on an AMD EPYC 7763
and Python 3.12.15. Its own machine report and numerical environment and package
versions are saved with its actual measurements.

| Check | Actual result |
|---|---:|
| Fixed scientific conditions | 192 of 192 |
| Actual recovery requests across all methods | 624 |
| Exact requests | 367 |
| Expected blocked requests at the declared budgets | 257 |
| Unexpected failures | 0 |
| Independent exact formulation comparisons | 8 matching minima |
| CPU PyTorch correctness tests in the neural job | 102 passed |

The two captured histories use Iris and Digits forest recipes and a previously
unused seed of 487. Budgets and loss scopes are frozen in
`configs/scientific_ci_oct15.json`. Repeated conditions and requests do not turn
these two histories into hundreds of independent workflow samples.

The original artifact ZIP is preserved at
`results/validation/2026-10-15/cloud_reproduction/fresh_cloud.zip` with SHA256
`ce0706de66fa3811c6f1cc59b6b1d35d8ee296113c5a428985d023be082329be`.
The download matched the hash reported by GitHub. The receipt and readable
analysis and machine files are beside it and the ZIP contains all original
raw request logs and capture inputs and exact runtime source copies.

This establishes fresh capture and exact recovery on a distinct cloud
environment. It does not establish exact replay of the old host's captured
blobs on a changed Python or numerical runtime. The strict environment guard
remains enabled. It also does not reproduce the entire paper or retinal or
gigabyte matrix on that cloud host. Those are separate scopes.

The generic runner's descriptive limitation text mentions eight captures
because it was written for the full main protocol. This cloud run actually
contains two histories as its configuration and numerical ledgers state.

The native smoke benchmark and the separate neural and boundary control job
also passed. The scientific result compares our declared contract through the
common executor and does not become a native full HELIX or HYPPO comparison.
