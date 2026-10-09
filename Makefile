.PHONY: test smoke benchmark analyze oracle iteration2 rubric new-data new-data-repeated planner-ablation
export PYTHONPATH := src
export OPENBLAS_NUM_THREADS := 1
export OMP_NUM_THREADS := 1

rubric:
	bash run_benchmarks.sh

new-data:
	python -m recoverml benchmark --config configs/new_data_oct9.json --out results/runs/new_data_oct9
	python -m recoverml.audit results/runs/new_data_oct9
	python -m recoverml analyze results/runs/new_data_oct9

new-data-repeated:
	python -m recoverml benchmark --config configs/new_data_repeated_oct9.json --out results/runs/new_data_repeated_oct9
	python -m recoverml.audit results/runs/new_data_repeated_oct9
	python -m recoverml analyze results/runs/new_data_repeated_oct9

planner-ablation:
	python -m recoverml.planner_ablation results/runs/new_data_repeated_oct9 results/runs/planner_ablation_oct9 --trials 30

test:
	python -m unittest discover -s tests -v

smoke:
	python -m recoverml benchmark --config configs/smoke.json --out results/runs/new_smoke

benchmark:
	python -m recoverml benchmark --config configs/preliminary.json --out results/runs/new_preliminary

analyze:
	python -m recoverml analyze results/runs/new_preliminary

oracle:
	python -c "from pathlib import Path; from recoverml.oracle_experiment import run_oracle; run_oracle(Path('results/runs/new_preliminary'))"

iteration2:
	python -m recoverml benchmark --config configs/iteration2.json --out results/runs/new_iteration2
	python -m recoverml.audit results/runs/new_iteration2
	python -m recoverml analyze results/runs/new_iteration2
	python -m recoverml.comparison results/runs/new_iteration2
	python -c "from pathlib import Path; from recoverml.oracle_experiment import run_oracle; run_oracle(Path('results/runs/new_iteration2'),('recoverability','recoverability_v2'))"
