# Paper completion status

Updated 10 October 2026

## Current position

The implementation and reproducibility package are close to complete for a course paper
The measured evidence is now strong enough to support a focused paper about exact replayability frontier reduction
The full manuscript has not yet been assembled in this repository

| Paper part | Readiness | Available material |
|---|---:|---|
| Problem and motivation | 70% | Recovering historical ML outputs under storage limits and opaque boundaries is defined |
| Related work | 60% | HELIX and LIMA and Kishu and ElasticNotebook and ExoFlow and CAPS are collected but the exact frontier claim needs a final novelty search |
| System design | 85% | Capture and content addressing and budget planning and exact restoration are implemented and documented |
| Algorithm and correctness | 80% | The frontier rule and conditions and proof argument are written and exhaustive oracle tests pass |
| Experimental method | 80% | Automated configurations and raw logs and hashes and statistical methods are available |
| Results | 80% | Storage and throughput and latency and public data and frontier scaling results are complete on one machine |
| Discussion and limitations | 50% | Main scope limits are known but need to be organized into paper form |
| Abstract and conclusion | 20% | Final text should be written only after the paper claim and evaluation table are fixed |
| Reproducibility appendix | 90% | Commands and pinned environment and checksums and raw traces and CI are available |
| Integrated manuscript | 25% | No complete paper source is stored in the repository yet |

The research and evidence are about 70 percent ready for a strong course paper
The actual written manuscript is about 25 percent ready because the material exists in separate reports but has not been combined
The overall complete paper is therefore about 55 to 60 percent ready

## Current defensible contribution

RecoverML combines content addressed ML artifacts and explicit replayability contracts and budgeted recovery planning and exact hash checked restoration
Its focused algorithmic contribution is an exact replayability frontier reduction for the load first planner
On 15 Iris histories the V4 formulation reduced a depth 128 model from 1256 variables to 69 and produced a 3.38 times median history level speedup over V2 while all 450 paired planner sets kept the same proven optimal objective

## Work required before the full paper

1. Search specifically for prior work that removes ancestry behind non replayable or materialized workflow boundaries
2. Add at least one real external or nondeterministic boundary instead of only the controlled external feature proxy
3. Test branching graphs with several opaque boundaries and hundreds or thousands of nodes
4. Repeat the main timing study on another machine
5. Build one final comparison table across full snapshots and target snapshots and full replay and V2 and V4
6. Assemble the introduction and related work and method and evaluation and discussion into the required paper format
7. Check every claim against a raw file and cite the primary sources

The first five items strengthen the research claim and the last two convert the research package into the final manuscript
