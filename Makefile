.PHONY: test smoke benchmark analyze oracle iteration2 rubric new-data new-data-repeated planner-ablation frontier-scaling neural-study topology-scaling pytorch-study boundary-controls oracle-audit capability-study capability-banknote capability-dual-banknote capability-scaling
export PYTHONPATH := src
export OPENBLAS_NUM_THREADS := 1
export OMP_NUM_THREADS := 1

rubric:
	bash run_benchmarks.sh

capability-study:
	python -m recoverml.capability_experiment --output results/runs/new_capability_study --seeds 2 --versions 12

capability-banknote:
	python -m recoverml.capability_experiment --output results/runs/new_capability_banknote --seeds 3 --versions 12 --datasets banknote

capability-dual-banknote:
	python -m recoverml.capability_experiment --output results/runs/new_capability_dual_banknote --seeds 3 --versions 12 --datasets banknote --dual-scalers

capability-scaling:
	python -m recoverml.capability_scaling --output results/runs/new_capability_scaling

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

frontier-scaling:
	python -m recoverml.frontier_scaling --config configs/frontier_scaling_oct10.json --out results/runs/frontier_scaling_oct10

neural-study:
	python -m recoverml benchmark --config configs/neural_oct11.json --out results/runs/neural_oct11
	python -m recoverml.audit results/runs/neural_oct11
	python -m recoverml analyze results/runs/neural_oct11

topology-scaling:
	python -m recoverml.topology_scaling --config configs/topology_scaling_oct11.json --out results/runs/topology_scaling_oct11

pytorch-study:
	python -m recoverml benchmark --config configs/pytorch_oct13.json --out results/runs/pytorch_oct13
	python -m recoverml.audit results/runs/pytorch_oct13
	python -m recoverml analyze results/runs/pytorch_oct13
	python -m recoverml.torch_checkpoint_audit --benchmark results/runs/pytorch_oct13 --out results/runs/pytorch_checkpoints_oct13

boundary-controls:
	python -m recoverml.boundary_controls --config configs/boundary_controls_oct13.json --out results/runs/boundary_controls_oct13

oracle-audit:
	python -m recoverml.oracle_audit --graphs 128 --out results/runs/oracle_oct13

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
