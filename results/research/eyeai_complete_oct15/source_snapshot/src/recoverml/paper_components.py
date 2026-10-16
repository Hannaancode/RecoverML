"""Exact component validation with shared labels and layered AND controls."""
import argparse,csv,gzip,itertools,json,time
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph,pack,unpack,digest,write_store
from .operators import execute
from .capability_scaling import build
from .capability_retention import optimize as ce,retained_bytes,contract,CapabilityRestorer
from .scenario_retention import optimize as direct
from .component_retention import optimize as decomposed

def layered(groups,k,width):
    graph,caps,_,_=build(groups,k,width=width,seed=2027);base=[t for ts in graph.targets.values() for t in ts];extra=[]
    for j in range(4):
        deps=base[2*j:2*j+2];values=[unpack(graph.archive[graph.nodes[t].blob]) for t in deps]
        mean=execute('mean_features',values,{})
        mid=graph.add('mean_features',deps,{'stage':j},mean,True,'and_stage',.001,j)
        params=dict(scale=.37,offset=.13);value=execute('affine_features',[mean],params)
        if digest(pack(value)) in graph.candidates:raise RuntimeError('Unexpected identity collision')
        target=graph.add('external_features',[mid],{'stage':j},value,False,'layered_target',.001,j);extra.append(target)
        for provider in (0,1):
            p={**params,'provider':provider};actual=execute('affine_features',[mean],p)
            if pack(actual)!=pack(value):raise RuntimeError('Provider output differs')
            nid=graph.add('affine_features',[mid],p,actual,True,'layered_provider'+str(provider),.001,j);caps[nid]='provider'+str(provider)
    graph.targets['layered']=extra;forced=set()
    for target in base:
        blob=graph.nodes[target].blob
        groups_of_roots={caps[n.id] for n in graph.nodes.values() if n.replayable and n.blob==blob
            and {graph.nodes[d].blob for d in n.deps}<=graph.roots and n.id in caps}
        if len(groups_of_roots)<=k:forced.add(blob)
    if k>=2:forced|={graph.nodes[t].blob for t in extra}
    return graph,caps,retained_bytes(graph,graph.roots|forced,caps,k)

def run(source,destination):
    destination.mkdir(parents=True,exist_ok=False);rows=[];planning=[];traces=[]
    original=json.loads((source/'report.json').read_text())
    with threadpool_limits(limits=1):
        for k in (1,2):
            path=source/'stores'/f'k{k}'/'expanded_exact';g=Graph.read(path/'manifest.json')
            caps=json.loads((path/'capability_contract.json').read_text())['capabilities']
            expected=next(r['retained_bytes'] for r in original['rows'] if r['policy']=='expanded_exact' and r['k']==k)
            for trial in range(5):
                clock=time.perf_counter();stamp=time.time_ns();selected,status,diag=decomposed(g,caps,k,time_limit_s=60.);elapsed=time.perf_counter()-clock
                if status!='ok' or not diag['storage_optimal'] or retained_bytes(g,selected,caps,k)!=expected:raise RuntimeError('Mixed real optimum differs')
                row=dict(family='mixed_real',groups=3,width=264,k=k,trial=trial,policy='decomposed',elapsed_s=elapsed,analytic_or_reference_match=True,components=diag['component_count'])
                rows.append(row);planning.append(dict(**row,start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),diagnostic=diag))
        for groups in (10,20,40):
            for width in (18,28):
                for k in (1,2):
                    g,caps,expected=layered(groups,k,width);selected=None
                    for trial in range(3):
                        methods=[('decomposed',decomposed),('counterexample',ce),('expanded_exact',direct)];methods=methods[trial:]+methods[:trial]
                        for name,solver in methods:
                            stamp=time.time_ns();clock=time.perf_counter();cpu=time.process_time();retained,status,diag=solver(g,caps,k,time_limit_s=60.);elapsed=time.perf_counter()-clock
                            if status!='ok' or not diag['storage_optimal'] or retained_bytes(g,retained,caps,k)!=expected:raise RuntimeError('Layered analytic minimum differs')
                            if name=='decomposed':selected=retained
                            row=dict(family='layered',groups=groups,width=width,k=k,trial=trial,policy=name,elapsed_s=elapsed,analytic_or_reference_match=True,components=diag.get('component_count'))
                            rows.append(row);planning.append(dict(**row,cpu_s=time.process_time()-cpu,start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),diagnostic=diag))
                            print(json.dumps(row),flush=True)
                    store=destination/'stores'/f'g{groups}-w{width}-k{k}';write_store(g,selected,store);(store/'capability_contract.json').write_bytes(contract(caps,k))
                    labels=sorted(set(caps.values()))
                    for count in range(k+1):
                        for lost in itertools.combinations(labels,count):
                            for version,targets in g.targets.items():
                                disk=Graph.read(store/'manifest.json');r=CapabilityRestorer(disk,store,caps,lost);stamp=time.time_ns();clock=time.perf_counter();values=r.version(version)
                                if not all(pack(v)==g.archive[g.nodes[t].blob] for v,t in zip(values,targets)):raise RuntimeError('Layered target bytes differ')
                                if any(e.get('producer') and caps.get(e['producer']) in lost for e in r.trace):raise RuntimeError('Disabled layered producer executed')
                                traces.append(dict(groups=groups,width=width,k=k,version=version,disabled=list(lost),exact=True,
                                    capture_archive_absent=not disk.archive,start_timestamp_ns=stamp,end_timestamp_ns=time.time_ns(),elapsed_s=time.perf_counter()-clock,events=r.trace))
    with (destination/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    for name,value in [('planning_trials',planning),('execution_traces',traces)]:
        (destination/(name+'.json.gz')).write_bytes(gzip.compress((json.dumps(value,indent=2)+'\n').encode(),mtime=0))
    report=dict(planner_runs=len(rows),real_planner_runs=10,layered_cases=12,exact_disk_requests=len(traces),all_byte_optima_match=True,
        source_sha256=digest(Path(__file__).read_bytes()),component_source_sha256=digest(Path(__file__).with_name('component_retention.py').read_bytes()),
        selector_sha256=digest(Path(__file__).with_name('robust_retention.py').read_bytes()),
        qualification='New layered AND graphs with shared failure labels and independent analytic minimum; mixed real validation uses existing manifests')
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.source,a.output),indent=2))
