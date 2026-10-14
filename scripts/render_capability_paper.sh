#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p output/pdf
pandoc paper/RecoverML_capability_loss.md --from markdown --standalone \
  --pdf-engine=pdflatex --resource-path=paper:. -o output/pdf/RecoverML_capability_loss.pdf
pdfinfo output/pdf/RecoverML_capability_loss.pdf
