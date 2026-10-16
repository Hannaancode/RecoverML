"""Generated scaling controls with analytic minimum-storage answers.

This intentionally constructed family includes self-alias producer cycles.
Useful alternatives occur in controlled fractions and are not natural data.
Unwitnessed opaque target blobs must be retained; witnessed targets can be
reconstructed directly from mandatory roots. This gives an independent byte
lower bound, avoiding use of the optimizer or certificate as its own oracle.
"""
import argparse
import json
import time
from pathlib import Path
import numpy as np
from .core import Graph, digest, pack, write_store
from .operators import execute
from .witness import WitnessRestorer
from .witness_optimizer import optimize


def run(destination,widths=(8,32,128),seeds=3):
    destination.mkdir(parents=True,exist_ok=False)
    rows,traces=[],[]
    for seed in range(seeds):
        rng=np.random.default_rng(seed)
        for width in widths:
            for fraction in (0.,.5,1.):
                graph=Graph()
                x=np.ascontiguousarray(rng.normal(size=(32,8)))
                root=graph.add('input',[],{},x,False,'source',0.,0,mandatory=True)
                mandatory=set(graph.roots); missing=set(); targets=[]
                for i in range(width):
                    params=dict(scale=1.+(i+1)/16,offset=(seed+1)/32)
                    value=execute('affine_features',[x],params)
                    original=graph.add('external_features',[root],{'i':i},value,False,'legacy',.001,i%3)
                    targets.append(original)
                    # This logical DAG edge becomes a physical self-loop.
                    graph.add('affine_features',[original],dict(scale=1.,offset=0.),
                              value,True,'identity',.001,i%3)
                    if i<int(width*fraction):
                        graph.add('affine_features',[root],params,value,True,'alternative',.001,i%3)
                    else:
                        missing.add(graph.nodes[original].blob)
                graph.targets={str(v):targets[v::3] for v in range(3)}
                analytic_bytes=graph.metadata_bytes()+sum(graph.sizes()[b] for b in mandatory|missing)
                baseline_bytes=graph.metadata_bytes()+sum(graph.sizes()[b] for b in mandatory|{graph.nodes[t].blob for t in targets})
                case=f'width{width:04d}-seed{seed}-fraction{fraction}'
                selected,status,diag=optimize(graph,time_limit_s=30.)
                if status!='ok' or not diag['storage_optimal'] or graph.size(selected)!=analytic_bytes:
                    raise RuntimeError(f'Analytic lower bound mismatch: {case} {status} {diag}')
                logical,logical_status,logical_diag=optimize(graph,alternative=False,time_limit_s=30.)
                if logical_status!='ok' or not logical_diag['storage_optimal'] or graph.size(logical)!=baseline_bytes:
                    raise RuntimeError('Logical analytic lower bound mismatch: '+case)
                store=destination/'stores'/case; write_store(graph,selected,store)
                disk=Graph.read(store/'manifest.json')
                for version,ts in graph.targets.items():
                    restorer=WitnessRestorer(disk,store); start=time.time_ns()
                    values=restorer.version(version)
                    if not all(pack(v)==graph.archive[graph.nodes[t].blob] for t,v in zip(ts,values)):
                        raise RuntimeError('Scaling recovery mismatch')
                    traces.append(dict(case=case,version=version,start_timestamp_ns=start,
                        end_timestamp_ns=time.time_ns(),exact=True,targets=len(ts),events=restorer.trace))
                rows.append(dict(case=case,width=width,seed=seed,alternative_fraction=fraction,
                    nodes=len(graph.nodes),physical_blobs=len(graph.candidates),
                    witnessed_minimum_bytes=analytic_bytes,logical_minimum_bytes=baseline_bytes,
                    solver=diag,logical_solver=logical_diag,analytic_match=True))
    (destination/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    (destination/'execution_traces.json').write_text(json.dumps(traces,indent=2)+'\n')
    summary=dict(cases=len(rows),exact_version_restores=len(traces),
        exact_target_restores=sum(t['targets'] for t in traces),maximum_nodes=max(r['nodes'] for r in rows),
        source_sha256=digest(Path(__file__).read_bytes()),
        optimizer_sha256=digest(Path(__file__).with_name('witness_optimizer.py').read_bytes()),
        qualification='Generated scaling and alias-cycle controls with an analytic storage lower bound')
    (destination/'provenance.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--widths',type=int,nargs='+',default=[8,32,128]);parser.add_argument('--seeds',type=int,default=3)
    args=parser.parse_args()
    if args.seeds<1 or min(args.widths)<3: parser.error('Positive seeds and widths at least three required')
    print(json.dumps(run(args.output,tuple(args.widths),args.seeds),indent=2))
