# Improvements and validation on 8 October 2026

Today we improved evidence checks and protected earlier results and all 31 automated tests passed
The original 5400 request experiment also passed the stronger audit
These are new code and validation changes and the earlier performance measurements keep their original dates

## Complete restore evidence

The audit now checks the complete trial matrix against config.json
It checks request IDs and version order and recorded times and actual latency values
It joins every operation to the captured graph and the selected storage plan
Loads must refer to retained artifacts and replay must follow its recorded dependencies
Memory reuse must follow an earlier production of the same node in the same request
Each successful request must include operations for every requested target
Resource samples must cover the measured trial and CPU counters must stay in order
File hashes are checked before the logs are parsed

This fixes a gap where a successful request could lose all its operation records while other requests still supplied records
The new tests refresh the file hashes after removing records so they check semantic completeness as well as changed bytes
Other tests alter a latency or remove a declared trial and confirm rejection
Validation uses explicit exceptions and remains active with python -O
Hashes and consistency checks do not provide an external attestation of execution

The implementation commit is ac48dcc7afefd7c152197a9a28268342f23e156a and its GitHub checks passed

## Safe benchmark folders

The runner now reserves a new output folder before it runs tests
An existing folder causes an immediate error and its tests.txt stays unchanged
This prevents a repeated command from replacing earlier validation evidence before a later benchmark stage refuses to run
Use a new path when running another experiment

```bash
bash run_benchmarks.sh results/my_new_run
```

Runner tests check preserved file bytes and failure handling and stage order
They use a fake Python command only to test shell orchestration and do not generate performance measurements
The real end to end Python fixture still captures and restores a small history with one and two workers

## Validation evidence

- results/validation/2026-10-08/tests.txt records 31 passing automated tests
- results/validation/2026-10-08/audit_existing_run.txt records the stronger audit of the original experiment
- The audit confirms 5400 exact requests and 54 trials and 2129 resource samples and 39600 operation records
- bash -n run_benchmarks.sh passed
- The package checksums are updated with these changes

The main experiment used 23 tests when it was first run on 7 October and that historical report remains unchanged
The current suite has 31 tests after adding the new evidence and runner regression checks

## Next plan

Run the same benchmark on the submission machine and compare its measured results
Profile environment validation and trace logging before changing worker performance
Add an opaque workload to the worker experiment and keep coverage alongside latency
