# What optimization does this retinal history actually need?

This is a post-protocol structural analysis prompted by the completed preflight. Its purpose is to challenge the necessity of the exact optimizer. It must not be presented as a predeclared additional competitor in the 540-row benchmark.

The constructed history has mandatory roots R and two feature outputs. The older feature output F is shared by the earlier models and the aligned feature output is shared by the later models. Each historical model has one training producer and each probability prediction has one prediction producer. The following special-case result assumes their physical hashes do not introduce alternative producers. That assumption must be checked against each captured graph.

Let O be the set of unique older model and prediction payloads. Let T be the set of all model and prediction payloads. Common metadata and contract bytes are fixed within each comparison.

| Availability contract and targets | Minimum selected payload set |
|---|---|
| All code available | R |
| Legacy extraction can be lost and models plus predictions are protected | The cheaper of R plus F and R plus O |
| Legacy extraction can be lost and historical features are protected too | R plus F |
| Training and prediction can both be lost | R plus T |

The first row follows because the roots are mandatory and every protected result can be replayed from them.

For legacy loss the older feature output cannot be recomputed. Any robust retained set either contains F or does not contain F. If it contains F then the older models and predictions can be replayed and retaining them adds unnecessary bytes. If it does not contain F then each older model must itself be retained and each older prediction must also be retained because its feature dependency remains unavailable. Therefore comparing those two byte sums is enough. If F is a protected target then retaining it is compulsory after its extractor is removed.

For the broad contract consider the allowed scenario where both training and prediction are removed. Every protected model and prediction must be retained because no replay producer remains. Keeping those targets is also sufficient in every less severe scenario. Requested features can still be recomputed because both feature extractors remain available under this contract.

These rules require a linear scan over model and prediction payload sizes. A MILP solver is not needed to choose the optimum for this particular topology. We will compare this rule against all available certified exact results and structurally verify its retained sets. If the comparisons agree then the correct interpretation is that the experiment demonstrates useful automatic retention and recovery while offering no evidence that its choices require sophisticated optimization.

The general RecoverML graph can have AND dependencies and shared processing groups across more complex branches. Those features are not sufficient by themselves to establish practical importance. Evidence of real workflows with interacting storage choices and a useful improvement over a strong simple baseline is still needed. Increasing the number or size of models alone does not create such evidence.
