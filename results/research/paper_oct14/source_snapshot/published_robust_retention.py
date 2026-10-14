"""Exact retention service with a declared, heuristic engine selection rule.

The cutoff is an engineering choice calibrated on the initial experiment and
evaluated on new graph sizes. It is not an oracle for the fastest solver.
Either engine must certify the same formal recovery and byte objective.
"""
import math
from .capability_retention import validate, optimize as counterexample
from .scenario_retention import optimize as expanded

DIRECT_SCENARIO_CUTOFF=64


def optimize(graph,capabilities,k,time_limit_s=30.):
    validate(graph,capabilities,k)
    groups=len(set(capabilities.values()))
    scenarios=sum(math.comb(groups,i) for i in range(min(k,groups)+1))
    method='expanded_exact' if scenarios<=DIRECT_SCENARIO_CUTOFF else 'counterexample'
    function=expanded if method=='expanded_exact' else counterexample
    retained,status,diagnostic=function(graph,capabilities,k,time_limit_s=time_limit_s)
    diagnostic=dict(diagnostic,selected_engine=method,allowed_scenarios=scenarios,
                    direct_scenario_cutoff=DIRECT_SCENARIO_CUTOFF)
    return retained,status,diagnostic
