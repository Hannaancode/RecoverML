.PHONY: test smoke benchmark analyze oracle iteration2
export PYTHONPATH := src
export OPENBLAS_NUM_THREADS := 1
export OMP_NUM_THREADS := 1

test:
	python -m unittest discover -s tests -v

smoke:
	python -m recoverml benchmark --config configs/smoke.json --out results/new_smoke

benchmark:
	python -m recoverml benchmark --config configs/preliminary.json --out results/new_preliminary

analyze:
	python -m recoverml analyze results/new_preliminary

oracle:
	python -c "from pathlib import Path; from recoverml.oracle_experiment import run_oracle; run_oracle(Path('results/new_preliminary'))"

iteration2:
	python -m recoverml benchmark --config configs/iteration2.json --out results/new_iteration2
	python -m recoverml.audit results/new_iteration2
	python -m recoverml analyze results/new_iteration2
	python -m recoverml.comparison results/new_iteration2
	python -c "from pathlib import Path; from recoverml.oracle_experiment import run_oracle; run_oracle(Path('results/new_iteration2'),('recoverability','recoverability_v2'))"
