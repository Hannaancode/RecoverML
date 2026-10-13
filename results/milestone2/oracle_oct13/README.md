# Independent exhaustive presolve audit

128 logical graphs contain physical aliases and shared dependencies and overlapping and duplicate targets
2048 physical subsets pass feasibility and objective projection checks and 1890 solver comparisons match the independent exhaustive optimum
The cost recursion calls neither Graph.coverage nor Graph.estimate nor the planner frontier construction
The generated graphs intentionally reuse four optional physical values to bound enumeration
This is independent verification code within the project and not an external reproduction

```bash
make oracle-audit
```
