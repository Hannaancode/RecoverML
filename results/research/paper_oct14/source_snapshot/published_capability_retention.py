"""Counterexample-guided retention for bounded replay-capability loss.

One retained physical set must preserve all historical targets after any loss
of at most k declared capability groups. Ungrouped replay remains available.
This uses standard Horn closure and MILP techniques. It does not claim to have
invented robust optimization, labeled cuts, or counterexample-guided synthesis.

The separation oracle finds a closed set containing retained blobs but missing
a target under a bounded capability loss. Such a closed set certifies failure
even for cyclic physical alias graphs. Its complement gives a valid storage
cut: every robust store must retain at least one blob outside that closed set.
The master has storage variables only, not scenario-expanded replay variables.
"""
from dataclasses import replace
import math
import time
from .core import Graph,canonical
from .witness import certificate, WitnessRestorer


def validate(graph,capabilities,k):
    if not isinstance(k,int) or k<0:
        raise ValueError('Capability loss bound must be a nonnegative integer')
    if not set(capabilities)<=set(graph.nodes):
        raise ValueError('Unknown capability node')
    if any(not isinstance(group,str) or not group for group in capabilities.values()):
        raise ValueError('Capability groups must be nonempty strings')


def contract(capabilities,k):
    return canonical(dict(schema=1,capabilities=capabilities,maximum_lost_groups=k,
        semantics='declared replay capability outages; retained files and ungrouped operators remain available'))


def retained_bytes(graph,retained,capabilities,k):
    return graph.size(retained)+len(contract(capabilities,k))


def restricted(graph,capabilities,disabled):
    """A runtime availability view; original manifest/provenance stays intact."""
    disabled=set(disabled)
    if not disabled<=set(capabilities.values()):
        raise ValueError('Unknown disabled capability')
    view=Graph(env=graph.env)
    view.nodes={nid:replace(n,replayable=n.replayable and capabilities.get(nid) not in disabled)
                for nid,n in graph.nodes.items()}
    view.targets={v:list(ts) for v,ts in graph.targets.items()}
    view.roots=set(graph.roots)
    return view


class CapabilityRestorer(WitnessRestorer):
    def __init__(self,graph,store,capabilities,disabled,verify_environment=True):
        from .capability_ops import execute
        self.disabled=sorted(disabled)
        super().__init__(restricted(graph,capabilities,disabled),store,
                         verify_environment=verify_environment,replay_execute=execute)


def solve(cost,lo,hi,constraints,time_limit_s):
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_matrix
    rr,cc,vv,lower,upper=[],[],[],[],[]
    for row,(terms,low,high) in enumerate(constraints):
        for col,value in terms.items():
            rr.append(row);cc.append(col);vv.append(value)
        lower.append(low);upper.append(high)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(constraints),len(cost))).tocsc()
    return milp(np.asarray(cost),integrality=np.ones(len(cost)),bounds=Bounds(lo,hi),
        constraints=LinearConstraint(matrix,lower,upper),
        options={'time_limit':time_limit_s,'mip_rel_gap':0.})


def counterexample(graph,retained,capabilities,k,time_limit_s=10.):
    """Find a minimum-cardinality disabling set that defeats a protected target.

    Horn implications describe closed supersets of the least grounded closure.
    Existence of such a superset missing a target is equivalent to that target
    being unreachable. No rank variables or failure-scenario enumeration are
    required here. A solver timeout is UNKNOWN, never a robustness certificate.
    """
    validate(graph,capabilities,k)
    if not set(retained)<=graph.candidates:
        raise ValueError('Unknown retained blob')
    targets={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
    if not targets:
        return dict(status='certified',reason='no protected targets',solver_s=0.)
    blobs=sorted(graph.candidates);groups=sorted(set(capabilities.values()))
    bi={b:i for i,b in enumerate(blobs)};fi={f:len(blobs)+i for i,f in enumerate(groups)}
    # Lexicographic objective: first minimize losses then maximize the closed
    # witness size. N+1 dominates every possible change of at most N closed
    # values and yields smaller, stronger necessary storage cuts.
    cost=[-1.]*len(blobs)+[float(len(blobs)+1)]*len(groups)
    lo=[float(b in retained) for b in blobs]+[0.]*len(groups)
    hi=[1.]*len(cost)
    constraints=[({fi[f]:1. for f in groups},-math.inf,float(k)),
                 ({bi[b]:1. for b in targets},-math.inf,float(len(targets)-1))]
    for node in graph.nodes.values():
        if not node.replayable: continue
        deps={graph.nodes[d].blob for d in node.deps}
        terms={bi[node.blob]:1.}
        for b in deps: terms[bi[b]]=terms.get(bi[b],0.)-1.
        group=capabilities.get(node.id)
        if group is not None: terms[fi[group]]=terms.get(fi[group],0.)+1.
        constraints.append((terms,1.-len(deps),math.inf))
    started=time.perf_counter();result=solve(cost,lo,hi,constraints,time_limit_s)
    diag=dict(solver_status=int(result.status),solver_message=result.message,
              solver_s=time.perf_counter()-started,variables=len(cost),constraints=len(constraints))
    if result.status==2:
        return dict(status='certified',reason='no bounded capability loss defeats recovery',**diag)
    if result.x is None:
        return dict(status='unknown',**diag)
    disabled={f for f in groups if result.x[fi[f]]>.5}
    closed={b for b in blobs if result.x[bi[b]]>.5}
    view=restricted(graph,capabilities,disabled)
    closed_valid=all(not n.replayable or
        not {graph.nodes[d].blob for d in n.deps}<=closed or n.blob in closed
        for n in view.nodes.values())
    ground=certificate(view,retained)
    valid=(len(disabled)<=k and set(retained)<=closed and not targets<=closed and
           closed_valid and not ground['complete'])
    if not valid: return dict(status='rejected',**diag)
    return dict(status='counterexample',disabled=sorted(disabled),closed=sorted(closed),
                storage_cut=sorted(graph.candidates-closed),
                unreachable_targets=sorted(targets-set(ground['available'])),
                minimum_failure_proved=result.status==0,postchecked=True,**diag)


def optimize(graph,capabilities,k,budget=None,time_limit_s=10.,max_iterations=1000):
    """Minimize stored bytes while certifying all losses of at most k groups.

    If every master optimum is proven and the final oracle proves infeasible,
    the returned retained set is a proved robust storage optimum. Every cut is
    necessary for robustness, so the master supplies a global byte lower bound.
    No incumbent is labeled robust until the separation oracle certifies it.
    """
    validate(graph,capabilities,k)
    if not math.isfinite(time_limit_s) or time_limit_s<=0 or max_iterations<1:
        raise ValueError('Positive time limit and iteration count required')
    blobs=sorted(graph.candidates);sizes=graph.sizes();index={b:i for i,b in enumerate(blobs)}
    metadata=graph.metadata_bytes()+len(contract(capabilities,k));cuts=[];history=[]
    if not blobs:
        valid=not any(graph.targets.values()) and (budget is None or metadata<=budget)
        return set(),'ok' if valid else 'proven_infeasible',dict(robust_certified=valid,storage_optimal=valid)
    cost=[sizes[b]/1024. for b in blobs]
    lo=[float(b in graph.roots) for b in blobs];hi=[1.]*len(blobs)
    retained=set(graph.roots)
    for iteration in range(max_iterations):
        constraints=[({index[b]:1. for b in cut},1.,math.inf) for cut in cuts]
        if budget is not None:
            constraints.append(({index[b]:sizes[b]/1024. for b in blobs},-math.inf,(budget-metadata)/1024.))
        started=time.perf_counter();master=solve(cost,lo,hi,constraints,time_limit_s)
        master_s=time.perf_counter()-started
        if master.status==2:
            return retained,'proven_infeasible',dict(robust_certified=False,storage_optimal=False,iterations=history)
        if master.status!=0 or master.x is None:
            return retained,'master_unknown',dict(robust_certified=False,storage_optimal=False,iterations=history)
        retained={b for b in blobs if master.x[index[b]]>.5}
        size=metadata+sum(sizes[b] for b in retained)
        if not graph.roots<=retained or (budget is not None and size>budget):
            return retained,'master_rejected',dict(robust_certified=False,storage_optimal=False,iterations=history)
        adversary=counterexample(graph,retained,capabilities,k,time_limit_s)
        history.append(dict(iteration=iteration,master_s=master_s,retained_bytes=size,
                            lower_bound_bytes=float(master.fun)*1024.+metadata,oracle=adversary))
        if adversary['status']=='certified':
            return retained,'ok',dict(robust_certified=True,storage_optimal=True,
                retained_bytes=size,capability_bound=k,capabilities=sorted(set(capabilities.values())),
                master_storage_variables=len(blobs),cuts=len(cuts),iterations=history)
        if adversary['status']!='counterexample':
            return retained,'oracle_unknown',dict(robust_certified=False,storage_optimal=False,iterations=history)
        cut=set(adversary['storage_cut'])
        if not cut or any(cut==previous for previous in cuts):
            return retained,'cut_rejected',dict(robust_certified=False,storage_optimal=False,iterations=history)
        cuts.append(cut)
    return retained,'iteration_limit',dict(robust_certified=False,storage_optimal=False,iterations=history)
