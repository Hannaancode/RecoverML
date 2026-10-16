# Research and implementation references

These sources are retained for the literature review and the next research stage
The current benchmark compares local baseline implementations and does not execute these published systems

- [LIMA â€” SIGMOD 2021](https://mboehm7.github.io/resources/sigmod2021a_lima.pdf)
- [HELIX â€” PVLDB 2019](https://www.vldb.org/pvldb/vol12/p446-xin.pdf)
- [Kishu â€” PVLDB 18](https://www.vldb.org/pvldb/vol18/p970-li.pdf)
- [CAPS â€” PVLDB 19](https://www.vldb.org/pvldb/vol19/p1427-kontaxakis.pdf)
- [ElasticNotebook](https://arxiv.org/abs/2309.11083)
- [ExoFlow â€” OSDI 2023](https://www.usenix.org/system/files/osdi23-zhuang.pdf)
- [FlorDB â€” CIDR 2025](https://vldb.org/cidrdb/papers/2025/p33-garcia.pdf)
- [Disdat â€” USENIX OpML 2019](https://www.usenix.org/conference/opml19/presentation/yocum)
- [Checkmate â€” MLSys 2020](https://proceedings.mlsys.org/paper_files/paper/2020/file/0b816ae8f06f8dd3543dc3d9ef196cab-Paper.pdf)
- [HELIX demonstration and slicing â€” PVLDB 2018](https://www.vldb.org/pvldb/vol11/p1958-xin.pdf)
- [PyTorch reproducibility](https://docs.pytorch.org/docs/stable/notes/randomness.html)
- [PyTorch serialization](https://docs.pytorch.org/docs/stable/notes/serialization.html)
- [20 Newsgroups dataset](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_20newsgroups.html)
- [Wisconsin dataset documentation](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_breast_cancer.html)
- [Digits dataset documentation](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html)
- [Iris dataset documentation](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_iris.html)
- [Wine dataset documentation](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html)
- [Controlling randomness in scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html#controlling-randomness)
- [SciPy mixed integer optimization API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)

The [planner design](PLANNER_V2.md) explains the implemented cost model and its scope
The [novelty audit](NOVELTY_AUDIT.md) compares the focused claim with the primary literature and records the exact distinction used in the paper
The [experiment reports](reports) preserve the measured comparisons and research interpretation

## Contribution-review follow-up (16 October 2026)

- [Hyppo EDBT 2025 system/demo](https://dsachar.net/publication/2025-edbt-kss/2025-edbt-kss.pdf): later history/discovery and reuse interface, separate from the pinned 2024 component experiment.
- [Primary-source register and exact review scope](../results/validation/2026-10-16/contribution_review/source_register.json).
- [Contribution decision](CONTRIBUTION_POSITIONING_OCT16.md), [internal review](INTERNAL_REVIEW_OCT16.md), and [genuine course-review preparation](COURSE_PEER_REVIEW_PACKET.md). Internal AI review is separate from actual course/human feedback.
