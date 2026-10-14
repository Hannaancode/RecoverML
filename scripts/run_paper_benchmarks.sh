#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
paper_run_root="${1:-results/runs/new_paper_matrix}"
if [[ -e "$paper_run_root" ]]; then
  echo "Choose a new output folder so existing evidence is preserved" >&2
  exit 1
fi
mkdir -p "$paper_run_root"
python -m recoverml.paper_benchmarks --suite tabular --seeds 3 --versions 12 --output "$paper_run_root/tabular"
python -m recoverml.paper_benchmarks --suite neural --seeds 2 --versions 4 --output "$paper_run_root/estimators"
python -m recoverml.paper_benchmarks --suite scaling --trials 5 --output "$paper_run_root/scaling"
python -m recoverml.paper_benchmarks --suite index --trials 7 \
  --scan-source results/research/paper_oct14/source_snapshot/witness_scan.py --output "$paper_run_root/index"
python -m recoverml.paper_benchmarks --suite dvc --seeds 2 --output "$paper_run_root/dvc"
python -m recoverml.paper_merged --output "$paper_run_root/merged"
python -m recoverml.paper_holdout --output "$paper_run_root/holdout"
python -m recoverml.paper_auto_real --source "$paper_run_root/merged" --output "$paper_run_root/auto_real"
python -m recoverml.paper_components --source "$paper_run_root/merged" --output "$paper_run_root/components"
python -m recoverml.paper_published --hyppo-cache "$paper_run_root/pinned_hyppo" --output "$paper_run_root/published"
python -m recoverml.paper_fault_scope --output "$paper_run_root/fault_scope"
python scripts/analyze_paper_benchmarks.py --input "$paper_run_root" --output "$paper_run_root/analysis"
python scripts/analyze_retention_extensions.py --input "$paper_run_root" --output "$paper_run_root/extension_analysis"
