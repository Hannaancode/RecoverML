"""Constructed import/export workflows with full model and prediction targets.

Actual scaler exports are imported without forcing output equality. Exactness
is discovered by hashing. The import stage is treated as an unavailable legacy
producer after capture. This is a capability-loss experiment, not evidence from
an independently collected production workflow. It compares minimum storage
under two different recovery semantics, not the existing latency planners.
"""
import argparse
import csv
import io
import json
import time
from pathlib import Path
import numpy as np
from sklearn.datasets import load_breast_cancer, load_iris, load_wine
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .core import Graph, DiskRestorer, RestoreError, digest, pack, write_store
from .operators import execute
from .witness import WitnessRestorer
from .witness_optimizer import optimize


def capture(name, seed, transport, versions):
    if name=='banknote':
        from sklearn.utils import Bunch
        source=Path(__file__).resolve().parents[2]/'data/uci_banknote/data_banknote_authentication.txt'
        matrix=np.loadtxt(source,delimiter=',')
        if matrix.shape!=(1372,5) or not np.isfinite(matrix).all() or set(matrix[:,-1])!={0.,1.}:
            raise ValueError('Unexpected UCI Banknote data')
        data=Bunch(data=matrix[:,:4],target=matrix[:,4].astype(np.int64))
    else:
        data={'breast_cancer':load_breast_cancer,'iris':load_iris,'wine':load_wine}[name]()
    x=np.ascontiguousarray(data.data,dtype=np.float64)
    y=np.ascontiguousarray(data.target,dtype=np.int64)
    graph=Graph(); values={}; export_hashes=[]
    def add(op,deps,params,scope,value=None,replayable=True,mandatory=False,version=0):
        started=time.perf_counter()
        if value is None: value=execute(op,[values[d] for d in deps],params)
        nid=graph.add(op,deps,params,value,replayable,scope,time.perf_counter()-started,
                      version,mandatory=mandatory)
        values[nid]=value
        return nid
    rx=add('input',[],{'dataset':name,'kind':'x'},'source',value=x,replayable=False,mandatory=True)
    ry=add('input',[],{'dataset':name,'kind':'y'},'source',value=y,replayable=False,mandatory=True)
    split=add('split',[],{'rows':len(x),'seed':seed},'membership')
    # An external sklearn transformer produces a real exported file.
    original=StandardScaler().fit(x[values[split][0]]).transform(x)
    stream=io.BytesIO() if transport=='npy' else io.StringIO()
    if transport=='npy':
        np.save(stream,original,allow_pickle=False); serialized=stream.getvalue()
        imported=np.load(io.BytesIO(serialized),allow_pickle=False)
    else:
        np.savetxt(stream,original,delimiter=',',fmt='%.17g' if transport=='csv17' else '%.6g')
        serialized=stream.getvalue().encode()
        imported=np.loadtxt(io.StringIO(serialized.decode()),delimiter=',')
    imported=np.ascontiguousarray(imported)
    export_hashes.append(digest(serialized))
    legacy=add('external_features',[rx,split],{'transport':transport,'file_hash':export_hashes[0]},
               'unavailable_legacy_import',value=imported,replayable=False)
    # A separate local analysis branch computes the standardization recipe.
    scaler=add('fit_scaler',[rx,split],{},'local_analysis')
    local=add('scale',[rx,scaler],{},'local_analysis')
    equal=graph.nodes[legacy].blob==graph.nodes[local].blob
    qualities=[]
    for version in range(versions):
        model=add('train',[legacy,ry,split],{'model':'logistic','C':.5+version*.25,
                    'seed':seed},'model',version=version)
        pred=add('predict',[model,legacy,split],{},'prediction',version=version)
        graph.targets[str(version)]=[model,pred]
        probability=values[pred]
        if not np.isfinite(probability).all(): raise RuntimeError('Nonfinite prediction')
        qualities.append(float(np.mean(values[model].predict(imported[values[split][1]])==y[values[split][1]])))
    return graph,dict(dataset=name,seed=seed,transport=transport,versions=versions,
        observed_exact_feature_witness=equal,source_x_sha256=digest(pack(x)),
        source_y_sha256=digest(pack(y)),export_sha256=export_hashes[0],
        accuracy=qualities,rows=len(x),columns=x.shape[1])


def run(destination,seeds=5,versions=3):
    destination.mkdir(parents=True,exist_ok=False)
    rows,traces,metadata=[],[],[]
    with threadpool_limits(limits=1):
        for dataset in ('breast_cancer','iris','wine'):
            for seed in range(seeds):
                for transport in ('npy','csv17','csv6'):
                    graph,info=capture(dataset,seed,transport,versions)
                    case=f'{dataset}-{seed:02d}-{transport}'
                    metadata.append(dict(case=case,**info))
                    selections={}
                    # Rotate solve order to reduce a fixed-order warmup effect.
                    policies=['logical','witness'] if seed%2==0 else ['witness','logical']
                    for policy in policies:
                        selected,status,diag=optimize(graph,alternative=policy=='witness',time_limit_s=30.)
                        if status!='ok' or not diag['storage_optimal']:
                            raise RuntimeError(f'{case} {policy} not proven optimal: {status} {diag}')
                        selections[policy]=(selected,diag)
                    row=dict(case=case,**{k:info[k] for k in ('dataset','seed','transport','observed_exact_feature_witness')},
                             targets=2*versions,logical_bytes=graph.size(selections['logical'][0]),
                             witness_bytes=graph.size(selections['witness'][0]),
                             baseline_at_witness_budget=0,witness_at_witness_budget=0)
                    for policy in policies:
                        retained,diag=selections[policy]
                        store=destination/'stores'/case/policy
                        write_store(graph,retained,store)
                        for version,targets in graph.targets.items():
                            disk=Graph.read(store/'manifest.json')
                            restorer=(DiskRestorer(disk,store) if policy=='logical' else WitnessRestorer(disk,store))
                            start=time.time_ns(); before=time.process_time()
                            values=restorer.version(version)
                            if not all(pack(v)==graph.archive[graph.nodes[t].blob] for t,v in zip(targets,values)):
                                raise RuntimeError('Exact recovery mismatch')
                            traces.append(dict(case=case,policy=policy,version=version,
                                start_timestamp_ns=start,end_timestamp_ns=time.time_ns(),
                                cpu_s=time.process_time()-before,exact=True,
                                events=restorer.trace,solver=diag))
                    witness_store=destination/'stores'/case/'witness'
                    for version in graph.targets:
                        disk=Graph.read(witness_store/'manifest.json')
                        try:
                            DiskRestorer(disk,witness_store).version(version)
                            row['baseline_at_witness_budget']+=1
                        except RestoreError: pass
                        WitnessRestorer(disk,witness_store).version(version)
                        row['witness_at_witness_budget']+=1
                    row['saved_bytes']=row['logical_bytes']-row['witness_bytes']
                    rows.append(row)
    with (destination/'summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (destination/'execution_traces.json').write_text(json.dumps(traces,indent=2)+'\n')
    provenance=dict(cases=metadata,exact_version_restores=len(traces),
        source_sha256=digest(Path(__file__).read_bytes()),
        optimizer_sha256=digest(Path(__file__).with_name('witness_optimizer.py').read_bytes()),
        witness_sha256=digest(Path(__file__).with_name('witness.py').read_bytes()),
        qualification='Constructed legacy-import capability-loss workflows; not independently observed production traces')
    (destination/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4))
    transports=['npy','csv17','csv6']
    for i,name in enumerate(('breast_cancer','iris','wine')):
        savings=[np.mean([100*r['saved_bytes']/r['logical_bytes'] for r in rows if r['dataset']==name and r['transport']==t]) for t in transports]
        ax.bar(np.arange(3)+(i-1)*.25,savings,width=.25,label=name)
    ax.set_xticks(range(3),transports);ax.set_ylabel('Total stored bytes saved (%)')
    ax.set_xlabel('Feature export and import format');ax.set_title('Full model and prediction recovery')
    ax.legend();fig.tight_layout();fig.savefig(destination/'storage_savings.png',dpi=180);plt.close(fig)
    return dict(cases=len(rows),exact_version_restores=len(traces),
                observed_exact_feature_witnesses=sum(r['observed_exact_feature_witness'] for r in rows))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,default=5);parser.add_argument('--versions',type=int,default=3)
    args=parser.parse_args()
    if args.seeds<1 or args.versions<1: parser.error('Positive seeds and versions required')
    print(json.dumps(run(args.output,args.seeds,args.versions),indent=2))
