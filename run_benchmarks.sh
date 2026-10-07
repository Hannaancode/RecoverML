#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
out="${1:-results/run_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$out"
python -m unittest discover -s tests -v > "$out/tests.txt" 2>&1
python -m recoverml benchmark --config configs/smoke.json --out "$out/storage"
python -m recoverml.audit "$out/storage"
python -m recoverml.performance --config configs/performance.json --out "$out/performance"
printf 'Complete results in %s\n' "$out"
