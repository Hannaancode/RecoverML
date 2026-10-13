#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p output/pdf
pandoc paper/RecoverML_draft.md --from markdown --standalone \
  --pdf-engine=pdflatex --resource-path=paper:. \
  -o output/pdf/RecoverML_paper.pdf
pdfinfo output/pdf/RecoverML_paper.pdf
