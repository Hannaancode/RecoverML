"""Prospective, budget-matched supplementary audit with all outcomes retained."""
import argparse
import csv
from dataclasses import replace
import gzip
import json
import math
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import time
from threadpoolctl import threadpool_limits
from .core import Graph, RestoreError, pack, digest, write_store, environment
from .witness import WitnessRestorer, certificate
from .capability_retention import contract, retained_bytes, restricted
from .component_retention import optimize as exact
from .scenario_retention import optimize as reference
from .robust_heuristics import select as heuristic, fault_sets
from .published_materializers import load_source, select as hyppo
from .helix_materializer import select as helix


def dump(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def io_counters():
    try:
        return {k:int(v) for k,v in (line.split(':') for line in Path('/proc/self/io').read_text().splitlines())}
    except (OSError,ValueError):return {}


def snapshots(g, caps, k, budget):
    selected=set(g.roots)
    for targets in g.targets.values():
        trial=selected|{g.nodes[t].blob for t in targets}
        if retained_bytes(g,trial,caps,k)<=budget:selected=trial
    return selected


def run(destination, protocol_path, hyppo_cache):
    from .scientific_workflows import capture, execute, caps_for
    destination.mkdir(parents=True,exist_ok=False)
    config=json.loads(protocol_path.read_text());dump(destination/'protocol.json',config)
    started=time.time_ns();rows=[];plans=[];failures=[];captures=[];sensitivity=[]
    source_dir=destination/'source_snapshot';source_dir.mkdir()
    source_hashes={}
    for p in sorted(Path(__file__).parent.glob('*.py')):
        shutil.copyfile(p,source_dir/p.name);source_hashes[p.name]=digest(p.read_bytes())
    stamp=dict(start_timestamp_ns=started,protocol_sha256=digest(protocol_path.read_bytes()),
        protocol_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
        environment=environment(),source_sha256=source_hashes,
        scope='Prospectively frozen constructed public-recipe histories on this host, not production traces or second-machine reproduction')
    dump(destination/'run_start.json',stamp)
    module=load_source(hyppo_cache)
    output=destination/'summary.csv';trace_path=destination/'execution_traces.jsonl.gz'
    with output.open('w') as summary,gzip.open(trace_path,'wt') as trace,threadpool_limits(limits=1):
        writer=None
        for workflow in config['workflows']:
            for seed in config['seeds']:
                history=f'{workflow}-{seed}';clock=time.perf_counter()
                try:g,info=capture(workflow,seed,config['versions'])
                except Exception as exc:
                    failures.append(dict(history=history,phase='capture',error=repr(exc)));dump(destination/'failures.json',failures);continue
                captures.append(dict(history=history,capture_s=time.perf_counter()-clock,**info))
                full=destination/'captures'/history;write_store(g,g.candidates,full)
                dump(full/'capture_info.json',info)
                for scope in config['capability_scopes']:
                    caps=caps_for(g,scope)
                    for k in config['loss_bounds']:
                        case=f'{history}-{scope}-k{k}';faults=fault_sets(caps,k)
                        fixed=retained_bytes(g,g.roots,caps,k)
                        all_targets={g.nodes[t].blob for ts in g.targets.values() for t in ts}
                        target_payload=sum(g.sizes()[b] for b in all_targets-g.roots)
                        optima={}
                        for name,solver in [('RecoverML_exact',exact),('scenario_exact',reference)]:
                            start=time.perf_counter()
                            try:
                                chosen,status,diag=solver(g,caps,k,time_limit_s=config['solver_time_limit_s'])
                                valid=(status=='ok' and diag.get('storage_optimal') and diag.get('robust_certified'))
                                optima[name]=(chosen,valid,time.perf_counter()-start,status)
                                plans.append(dict(case=case,policy=name,status=status,diagnostic=diag,selected=sorted(chosen),
                                    actual_bytes=retained_bytes(g,chosen,caps,k),planning_s=optima[name][2]))
                            except Exception as exc:
                                failures.append(dict(case=case,phase='planning',policy=name,error=repr(exc)))
                                optima[name]=(set(g.roots),False,time.perf_counter()-start,'exception')
                        if all(o[1] for o in optima.values()):
                            if len({retained_bytes(g,o[0],caps,k) for o in optima.values()})!=1:
                                failures.append(dict(case=case,phase='optimum_disagreement'))
                        for fraction in config['optional_snapshot_budget_fractions']:
                            budget=fixed+math.floor(fraction*target_payload);optional=budget-fixed
                            order=list(config['methods']);rotation=(seed+k+int(fraction*100))%len(order)
                            order=order[rotation:]+order[:rotation]
                            for policy in order:
                                pstart=time.perf_counter();status='heuristic';diag={}
                                try:
                                    if policy in optima:
                                        chosen,valid,planning_s,status=optima[policy]
                                        if not valid or retained_bytes(g,chosen,caps,k)>budget:
                                            chosen=set(g.roots);status='minimum_exceeds_budget' if valid else status
                                    elif policy.startswith('robust_'):
                                        chosen,diag=heuristic(g,caps,k,budget,policy=='robust_local');planning_s=time.perf_counter()-pstart
                                    elif policy.startswith('HYPPO'):
                                        chosen=hyppo(g,optional,module,policy=='HYPPO_frequency');planning_s=time.perf_counter()-pstart
                                    elif policy=='HELIX_rule':
                                        chosen,diag=helix(g,optional,config['helix_read_MiB_s']*1024**2);planning_s=time.perf_counter()-pstart
                                    else:chosen=snapshots(g,caps,k,budget);planning_s=time.perf_counter()-pstart
                                except Exception as exc:
                                    failures.append(dict(case=case,policy=policy,budget=budget,phase='selection',error=repr(exc)))
                                    chosen=set(g.roots);status='selection_exception';planning_s=time.perf_counter()-pstart
                                actual=retained_bytes(g,chosen,caps,k)
                                if actual>budget:raise RuntimeError('Budget invariant violated')
                                plans.append(dict(case=case,policy=policy,budget_fraction=fraction,budget=budget,status=status,
                                    selected=sorted(chosen),actual_bytes=actual,planning_s=planning_s,diagnostic=diag))
                                exact_count=blocked=unexpected=0;latencies=[];cpus=[];read_io=write_io=0;operations=0
                                with tempfile.TemporaryDirectory(prefix='recoverml_audit_') as temp:
                                    store=Path(temp)/'store';write_store(g,chosen,store);(store/'capability_contract.json').write_bytes(contract(caps,k))
                                    on_disk=sum(p.stat().st_size for p in store.rglob('*') if p.is_file())
                                    if on_disk!=actual:raise RuntimeError('Physical storage accounting differs')
                                    for lost in faults:
                                        for version,targets in g.targets.items():
                                            ns=time.time_ns();clock=time.perf_counter();cpu=time.process_time();before_io=io_counters()
                                            error=None;ok=False;r=None
                                            disk=Graph.read(store/'manifest.json');view=restricted(disk,caps,lost)
                                            expected=certificate(view,chosen)['version_coverage'][version]
                                            try:
                                                r=WitnessRestorer(view,store,replay_execute=execute);values=r.version(version)
                                                ok=all(pack(v)==g.archive[g.nodes[t].blob] for v,t in zip(values,targets))
                                                if not ok:error='Final target bytes mismatch'
                                            except Exception as exc:error=type(exc).__name__+': '+str(exc)
                                            latency=time.perf_counter()-clock;used=time.process_time()-cpu;after_io=io_counters()
                                            is_blocked=bool(error) and not expected and isinstance(error,str) and error.startswith('RestoreError:')
                                            is_unexpected=(not ok and not is_blocked) or (ok and not expected)
                                            exact_count+=int(ok);blocked+=int(is_blocked);unexpected+=int(is_unexpected)
                                            events=[] if r is None else r.trace;operations+=len(events)
                                            if any(e.get('producer') and caps.get(e['producer']) in lost for e in events):
                                                raise RuntimeError('Disabled producer executed')
                                            delta={n:after_io[n]-before_io.get(n,0) for n in after_io}
                                            read_io+=delta.get('read_bytes',0);write_io+=delta.get('write_bytes',0)
                                            latencies.append(latency);cpus.append(used)
                                            record=dict(case=case,history=history,policy=policy,budget_fraction=fraction,budget_bytes=budget,
                                                version=version,disabled=list(lost),expected_recoverable=expected,exact=ok,expected_blocked=is_blocked,
                                                unexpected=is_unexpected,error=error,start_timestamp_ns=ns,end_timestamp_ns=time.time_ns(),
                                                latency_s=latency,cpu_s=used,io_delta=delta,process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                                capture_archive_absent=not disk.archive,events=events)
                                            trace.write(json.dumps(record,allow_nan=False)+'\n')
                                import numpy as np
                                row=dict(case=case,history=history,workflow=workflow,seed=seed,scope=scope,k=k,policy=policy,
                                    budget_fraction=fraction,budget_bytes=budget,retained_bytes=actual,fixed_bytes=fixed,
                                    optional_payload_bytes=actual-fixed,snapshot_target_payload_bytes=target_payload,
                                    planning_status=status,planning_s=planning_s,requests=len(latencies),exact=exact_count,
                                    blocked=blocked,unexpected=unexpected,complete=exact_count==len(latencies),
                                    latency_mean_s=float(np.mean(latencies)),latency_p50_s=float(np.quantile(latencies,.5)),
                                    latency_p90_s=float(np.quantile(latencies,.9)),latency_p99_s=float(np.quantile(latencies,.99)),
                                    cpu_total_s=sum(cpus),read_bytes=read_io,write_bytes=write_io,operation_events=operations,
                                    process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                                if writer is None:writer=csv.DictWriter(summary,fieldnames=list(row),lineterminator='\n');writer.writeheader()
                                writer.writerow(row);summary.flush();rows.append(row)
                            # The full sensitivity grid changes only decision annotations.
                            for multiplier in config['sensitivity']['capture_cost_multipliers']:
                                proxy=Graph(env=g.env);proxy.nodes={n:replace(v,compute_s=v.compute_s*multiplier) for n,v in g.nodes.items()}
                                proxy.targets=g.targets;proxy.roots=g.roots
                                for reverse in (False,True):
                                    sels={}
                                    for frequency in (False,True):
                                        sels['HYPPO_frequency' if frequency else 'HYPPO_rank']=hyppo(proxy,optional,module,frequency)
                                    # HELIX has a genuine capture-event tie ordering.
                                    for speed in config['sensitivity']['HELIX_read_MiB_s']:
                                        sels['HELIX_'+str(speed)]=helix(proxy,optional,speed*1024**2,reverse)[0]
                                    # HYPPO native tie order is unchanged; do not claim it changed.
                                    sels['robust_greedy']=heuristic(g,caps,k,budget,reverse_ties=reverse)[0]
                                    for name,selected in sels.items():
                                        count=sum(sum(certificate(restricted(g,caps,f),selected)['version_coverage'].values()) for f in faults)
                                        sensitivity.append(dict(case=case,budget_fraction=fraction,cost_multiplier=multiplier,
                                            tie_order='reverse_hash_or_event' if reverse else 'hash_or_capture',
                                            tie_applies=name.startswith('HELIX') or name=='robust_greedy',policy=name,
                                            retained_bytes=retained_bytes(g,selected,caps,k),budget_bytes=budget,
                                            exact_structural_requests=count,total_requests=len(faults)*len(g.targets)))
                        print(json.dumps(dict(completed_case=case,rows=len(rows),failures=len(failures))),flush=True)
                        dump(destination/'failures.json',failures)
    for name,value in [('planner_records',plans),('sensitivity',sensitivity)]:
        with gzip.open(destination/(name+'.json.gz'),'wt') as stream:json.dump(value,stream,allow_nan=False)
    dump(destination/'capture_inventory.json',captures)
    # Compress all unique captured bytes once, not one redundant store per policy.
    import tarfile
    with tarfile.open(destination/'captures.tar.gz','w:gz') as stream:stream.add(destination/'captures',arcname='captures')
    shutil.rmtree(destination/'captures')
    changed=[n for n,h in source_hashes.items() if digest(Path(__file__).with_name(n).read_bytes())!=h]
    report=dict(histories=len(captures),case_policy_budget_rows=len(rows),requests=sum(r['requests'] for r in rows),
        exact=sum(r['exact'] for r in rows),expected_blocked=sum(r['blocked'] for r in rows),unexpected=sum(r['unexpected'] for r in rows),
        failures=failures,source_changed_during_run=changed,sensitivity_rows=len(sensitivity),
        finish_timestamp_ns=time.time_ns(),raw_trace_sha256=digest(trace_path.read_bytes()),
        limitations=['Eight constructed captures are not a random production sample','Repeated requests are correlated',
            'Exact minima do not maximize partial coverage below their feasibility budget',
            'One recovery trial per request; process high-water memory and cached Linux I/O are descriptive',
            'No GPU, energy or cross-machine result is claimed'])
    dump(destination/'report.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--protocol',type=Path,default=Path('configs/scientific_audit_oct15.json'))
    p.add_argument('--hyppo-cache',type=Path,required=True);a=p.parse_args()
    print(json.dumps(run(a.output,a.protocol,a.hyppo_cache),indent=2))
