# RecoverML Overleaf project

Upload the ZIP as a new Overleaf project, set the main file to
`RecoverML_paper_revised.tex`, choose **XeLaTeX**, and recompile. BibTeX will
run for the reference list.

The main paper uses seven vector figures: four charts rebuilt from saved study
ledgers, a chart rebuilt from the audited final runtime run, a vector redraw
of the supplied architecture diagram, and a Letter storage chart rebuilt from
its saved analysis JSON. The original `methodology_user.png` remains in `figures/` so
the redraw can be checked against it. Keep the `figures/` and `fonts/`
folders intact. The ZIP also contains a locally compiled PDF in `reference/`
for comparison; Overleaf generates its own PDF.

The paper's experimental data and executable recovery system are in the
[RecoverML repository](https://github.com/Hannaancode/RecoverML). Those raw
ledgers are separate from the LaTeX build assets and are not required for
Overleaf compilation. The runtime raw artifact is permanently saved in
`results/research/runtime_scaling_oct30/evidence.zip`, and
`python scripts/rebuild_revised_paper.py` rebuilds the figures and PDF from
the repository. The updated paper uses the author's writing rules,
short captions, and a separate limitations section.
