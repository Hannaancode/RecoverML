"""Measured concurrent disk restores with isolated request state and Linux resource traces.

The page cache is warm. Each request has its own restorer and includes environment
validation. Planning and capture are outside restore throughput measurements.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import random
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from .benchmark import write_csv
from .core import Graph, DiskRestorer, canonical, write_store
from .policies import select
from .workloads import build_history


def utc():
    return datetime.now(timezone.utc).isoformat()


class Resources:
    """Process CPU time and resident bytes sampled while a measured trial runs."""
    def __init__(self, trial, interval=0.02):
        self.trial, self.interval = trial, interval
        self.rows = []
        self.stop = threading.Event()

    def sample(self):
        now, cpu = time.perf_counter_ns(), time.process_time_ns()
        rss = int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        previous = self.rows[-1] if self.rows else None
        percent = (100 * (cpu-previous['cpu_ns']) / (now-previous['monotonic_ns'])) if previous else 0.0
        self.rows.append(dict(trial=self.trial, utc=utc(), monotonic_ns=now,
                              cpu_ns=cpu, cpu_percent_one_core=percent, rss_bytes=rss))

    def __enter__(self):
        self.sample()
        def loop():
            while not self.stop.wait(self.interval):
                self.sample()
        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.sample()


def restore_request(graph, store, trial, index, version, submitted_ns, submitted_utc):
    started_ns, started_utc = time.perf_counter_ns(), utc()
    restorer = None
    error = ''
    try:
        restorer = DiskRestorer(graph, store)
        restorer.version(version)
        exact = True
    except Exception as exc:
        exact, error = False, f'{type(exc).__name__}: {exc}'
    ended_ns, ended_utc = time.perf_counter_ns(), utc()
    row = dict(trial=trial, request_id=index, version=version,
               submitted_utc=submitted_utc, started_utc=started_utc, ended_utc=ended_utc,
               submitted_ns=submitted_ns, started_ns=started_ns, ended_ns=ended_ns,
               queue_ms=(started_ns-submitted_ns)/1e6,
               service_ms=(ended_ns-started_ns)/1e6,
               response_ms=(ended_ns-submitted_ns)/1e6, exact=exact, error=error)
    traces = [dict(trial=trial, request_id=index, **t) for t in restorer.trace] if restorer else []
    return row, traces


def audit(out):
    """Check file identity and the declared experiment and each restore path.

    Explicit exceptions keep validation active under python -O. Hashes detect
    changed bytes; graph checks also catch incomplete logs with refreshed hashes.
    Neither mechanism is an external attestation of execution.
    """
    out = Path(out)
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    required = {'config.json', 'captures.json', 'plans.json', 'provenance.json',
                'requests.csv', 'summary.csv', 'resources.csv', 'operations.jsonl.gz',
                'throughput_vs_concurrency.png', 'latency_cdf.png'}
    hashes = json.loads((out/'HASHES.json').read_text())
    require(required <= hashes.keys(), 'Hash manifest is missing required evidence')
    for path, expected in hashes.items():
        require(Path(path).name == path, 'Evidence paths must be local filenames')
        require(hashlib.sha256((out/path).read_bytes()).hexdigest() == expected,
                f'File hash mismatch: {path}')
    def read(name):
        with (out/name).open() as stream:
            return list(csv.DictReader(stream))
    requests = read('requests.csv')
    summaries = read('summary.csv')
    resources = read('resources.csv')
    cfg = json.loads((out/'config.json').read_text())
    expected = {
        f'rows{scale}-{policy}-w{workers}-rep{repeat}': (scale,policy,workers,repeat)
        for scale in cfg['rows'] for policy in cfg['policies']
        for workers in cfg['workers'] for repeat in range(cfg['repeats'])
    }
    trials = {s['trial']: s for s in summaries}
    require(bool(expected) and len(trials) == len(summaries) and trials.keys() == expected.keys(),
            'Summary does not match the declared trial matrix')
    require(len(requests) == len(expected)*cfg['requests'], 'Request matrix is incomplete')
    keys = {(r['trial'],int(r['request_id'])): r for r in requests}
    require(len(keys) == len(requests), 'Duplicate request identity')
    require(all(r['trial'] in trials for r in requests+resources), 'Unknown trial in raw logs')
    captures = {c['rows']: c['manifest'] for c in json.loads((out/'captures.json').read_text())}
    require(captures.keys() == set(cfg['rows']), 'Captured histories do not match data scales')
    plans_list = json.loads((out/'plans.json').read_text())
    plans = {p['trial']: p for p in plans_list}
    require(len(plans) == len(plans_list) and plans.keys() == trials.keys(), 'Plan matrix is incomplete')
    for trial, s in trials.items():
        scale, policy, workers, repeat = expected[trial]
        require((int(s['rows']),s['policy'],int(s['workers']),int(s['repeat'])) ==
                (scale,policy,workers,repeat), f'Trial settings mismatch: {trial}')
        rows = [r for r in requests if r['trial'] == trial]
        require(len(rows) == int(s['completed_requests']) == int(s['submitted_requests']) == cfg['requests'],
                f'Request counters mismatch: {trial}')
        require({int(r['request_id']) for r in rows} == set(range(cfg['requests'])),
                f'Request IDs mismatch: {trial}')
        require(sum(r['exact']=='True' for r in rows) == int(s['exact_requests']),
                f'Exact counters mismatch: {trial}')
        start, end = int(s['started_ns']), int(s['ended_ns'])
        require(start < end, f'Invalid trial duration: {trial}')
        for r in rows:
            require(r['version'] == str(int(r['request_id']) % cfg['versions']),
                    f'Version schedule mismatch: {trial}')
            submitted, started, ended = (int(r[k]) for k in ('submitted_ns','started_ns','ended_ns'))
            require(start <= submitted <= started <= ended <= end, f'Timestamp order mismatch: {trial}')
            for field in ('submitted_utc','started_utc','ended_utc'):
                require(datetime.fromisoformat(r[field]).utcoffset() is not None, 'UTC timestamp lacks timezone')
            for field, actual in (('queue_ms',(started-submitted)/1e6),
                                  ('service_ms',(ended-started)/1e6),
                                  ('response_ms',(ended-submitted)/1e6)):
                require(abs(float(r[field])-actual) < 1e-6, f'Latency mismatch: {trial} {field}')
            require(r['exact'] in ('True','False'), 'Invalid exact flag')
            require(r['exact'] != 'True' or not r['error'], 'Exact request has an error')
        samples = [r for r in resources if r['trial'] == trial]
        require(len(samples) >= 2 and all(int(r['rss_bytes']) > 0 for r in samples),
                f'Missing resource samples: {trial}')
        require(int(samples[0]['monotonic_ns']) <= start and int(samples[-1]['monotonic_ns']) >= end,
                f'Resource samples do not bracket trial: {trial}')
        require(all(int(a['monotonic_ns']) < int(b['monotonic_ns']) and int(a['cpu_ns']) <= int(b['cpu_ns'])
                    for a,b in zip(samples,samples[1:])), f'Resource clock order mismatch: {trial}')
        elapsed = (end-start)/1e9
        require(abs(float(s['elapsed_s'])-elapsed) < 1e-6 and
                abs(float(s['throughput_rps'])-int(s['exact_requests'])/elapsed) < 1e-6,
                f'Throughput mismatch: {trial}')
        for metric in ('service','response'):
            vals = [float(r[metric+'_ms']) for r in rows if r['exact']=='True']
            for q in (50,90,99):
                recorded = s[f'{metric}_p{q}_ms']
                require(abs(float(recorded)-float(np.percentile(vals,q))) < 1e-6
                        if vals else recorded == '', f'Percentile mismatch: {trial}')
    with gzip.open(out/'operations.jsonl.gz','rt') as stream:
        operations = [json.loads(line) for line in stream]
    produced = {key: set() for key in keys}
    nodes = {scale: {n['id']:n for n in manifest['nodes']} for scale,manifest in captures.items()}
    for op in operations:
        key = (op['trial'],op['request_id'])
        require(key in keys and op['exact'] is True, 'Unknown or non-exact operation')
        scale = expected[op['trial']][0]
        require(op['node'] in nodes[scale], 'Unknown operation node')
        node = nodes[scale][op['node']]
        retained = set(plans[op['trial']]['retained'])
        action = op['action']
        require(action in ('load','replay','memory_reuse'), 'Unknown operation action')
        require(float(op['elapsed_s']) >= 0 and float(op['verify_s']) >= 0, 'Invalid operation duration')
        if action == 'memory_reuse':
            require(op['node'] in produced[key], 'Reuse precedes production')
        elif action == 'load':
            require(node['blob'] in retained and op['bytes'] == node['size'], 'Load not supported by retained plan')
        else:
            require(node['blob'] not in retained and node['replayable'] and
                    set(node['deps']) <= produced[key] and op['bytes'] == node['size'],
                    'Replay lacks its recorded dependencies')
        produced[key].add(op['node'])
    for key, request in keys.items():
        if request['exact'] == 'True':
            manifest = captures[expected[request['trial']][0]]
            require(set(manifest['targets'][request['version']]) <= produced[key],
                    f'Successful request is missing target operations: {key}')
    report = dict(passed=True, requests=len(requests), trials=len(summaries),
                  exact_requests=sum(r['exact']=='True' for r in requests),
                  resource_samples=len(resources), operation_records=len(operations))
    (out/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def plot(out, summaries, requests):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scales = sorted({s['rows'] for s in summaries})
    policies = sorted({s['policy'] for s in summaries})
    fig, axes = plt.subplots(1,len(scales),figsize=(6*len(scales),4),squeeze=False)
    for ax, scale in zip(axes[0],scales):
        for policy in policies:
            groups = {}
            for s in summaries:
                if s['rows']==scale and s['policy']==policy:
                    groups.setdefault(s['workers'],[]).append(s['throughput_rps'])
            xs = sorted(groups)
            ax.errorbar(xs,[np.mean(groups[x]) for x in xs],
                        yerr=[np.std(groups[x]) for x in xs],marker='o',capsize=4,label=policy)
        ax.set(title=f'{scale:,} rows · warm page cache',xlabel='Concurrent workers',ylabel='Exact restores / second')
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out/'throughput_vs_concurrency.png',dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1,len(scales),figsize=(6*len(scales),4),squeeze=False)
    for ax, scale in zip(axes[0],scales):
        for policy in policies:
            ids={s['trial'] for s in summaries if s['rows']==scale and s['policy']==policy and s['workers']==1}
            vals=sorted(r['service_ms'] for r in requests if r['trial'] in ids and r['exact'])
            if vals:
                ax.step(vals,np.arange(1,len(vals)+1)/len(vals),where='post',label=f'{policy} (n={len(vals)})')
        ax.set(title=f'{scale:,} rows · 1 worker',xlabel='Service latency (ms) · log scale',ylabel='Fraction of exact requests')
        ax.set_xscale('log')
        ax.set_ylim(0,1.02)
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out/'latency_cdf.png',dpi=170)
    plt.close(fig)


def run(config_path, out):
    if platform.system() != 'Linux':
        raise RuntimeError('Resource tracing requires Linux /proc; use a Linux VM or WSL')
    cfg = json.loads(Path(config_path).read_text())
    if min(cfg['rows']+cfg['workers']+[cfg['requests'],cfg['repeats'],cfg['versions']]) < 1:
        raise ValueError('Experiment sizes must be positive')
    out = Path(out)
    out.mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_bytes(canonical(cfg))
    source=Path(__file__).parent
    provenance = dict(started_utc=utc(), platform=platform.platform(), cpu_count=os.cpu_count(),
                      cpuinfo=Path('/proc/cpuinfo').read_text().split('\n\n')[0],
                      cgroup_cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip() if Path('/sys/fs/cgroup/cpu.max').exists() else None,
                      source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob('*.py'))},
                      latency_scope='Service includes environment check and disk restore with hash checks; response also includes executor queue wait',
                      cache='Warm OS page cache; fresh request memo; one BLAS thread per worker',
                      resource_scope='Whole benchmark process including sampler and executor; CPU percent is relative to one core',
                      throughput_scope='Exact requests divided by submission-to-completion wall time; capture and planning excluded')
    requests, summaries, samples, plans, captures = [],[],[],[],[]
    with threadpool_limits(limits=1), gzip.open(out/'operations.jsonl.gz','wt') as operations:
        for scale in cfg['rows']:
            settings=dict(dataset='synthetic',rows=scale,versions=cfg['versions'],model='logistic',change='parameters',boundary='deterministic')
            graph, info = build_history(settings,seed=100)
            captures.append(dict(rows=scale,settings=settings,metrics=info,manifest=graph.manifest()))
            jobs=[(p,w,r) for p in cfg['policies'] for w in cfg['workers'] for r in range(cfg['repeats'])]
            random.Random(100+scale).shuffle(jobs)
            for policy, workers, repeat in jobs:
                trial=f'rows{scale}-{policy}-w{workers}-rep{repeat}'
                budget=graph.size(graph.candidates)
                selection=select(graph,policy,budget)
                assert selection.status=='ok' and graph.coverage(selection.retained)[0]
                store=out/'work'/trial
                write_store(graph,selection.retained,store)
                replay=Graph.read(store/'manifest.json')
                assert not replay.archive
                plans.append(dict(trial=trial,policy=policy,budget_bytes=budget,retained_bytes=graph.size(selection.retained),
                                  retained=sorted(selection.retained),planning_s=selection.planning_s,status=selection.status))
                # Warm each version before the timed trial; warmups are not counted.
                for v in range(cfg['versions']):
                    DiskRestorer(replay,store).version(str(v))
                with Resources(trial) as resource:
                    start, start_utc = time.perf_counter_ns(), utc()
                    cpu_start=time.process_time_ns()
                    with ThreadPoolExecutor(max_workers=workers) as executor:
                        futures=[]
                        for i in range(cfg['requests']):
                            submitted, stamp = time.perf_counter_ns(), utc()
                            futures.append(executor.submit(restore_request,replay,store,trial,i,str(i%cfg['versions']),submitted,stamp))
                        rows=[]
                        for f in futures:
                            row, trace=f.result()
                            rows.append(row)
                            for t in trace:
                                operations.write(json.dumps(t)+'\n')
                    end, end_utc = time.perf_counter_ns(), utc()
                    cpu_end=time.process_time_ns()
                samples.extend(resource.rows)
                requests.extend(rows)
                good=[r for r in rows if r['exact']]
                summary=dict(trial=trial,rows=scale,policy=policy,workers=workers,repeat=repeat,
                             budget_bytes=budget,retained_bytes=graph.size(selection.retained),
                             started_utc=start_utc,ended_utc=end_utc,started_ns=start,ended_ns=end,
                             submitted_requests=cfg['requests'],completed_requests=len(rows),exact_requests=len(good),
                             elapsed_s=(end-start)/1e9,cpu_s=(cpu_end-cpu_start)/1e9,
                             throughput_rps=len(good)/((end-start)/1e9),peak_sampled_rss_bytes=max(s['rss_bytes'] for s in resource.rows))
                for metric in ('service','response'):
                    for q in (50,90,99):
                        summary[f'{metric}_p{q}_ms']=float(np.percentile([r[metric+'_ms'] for r in good],q)) if good else None
                summaries.append(summary)
                print(f'{trial}: {len(good)}/{len(rows)} exact · {summary["throughput_rps"]:.1f} req/s',flush=True)
                shutil.rmtree(store)
            provenance['environment']=graph.env
    shutil.rmtree(out/'work')
    for name,rows in [('requests',requests),('summary',summaries),('resources',samples)]:
        write_csv(out/f'{name}.csv',rows)
    (out/'plans.json').write_text(json.dumps(plans,indent=2)+'\n')
    (out/'captures.json').write_text(json.dumps(captures,indent=2)+'\n')
    provenance['ended_utc']=utc()
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    plot(out,summaries,requests)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
    report=audit(out)
    if report['exact_requests'] != report['requests']:
        raise RuntimeError('Measured restore failures; inspect request error fields')
    (out/'RUN_COMPLETE').write_text(utc()+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='configs/performance.json')
    parser.add_argument('--out',required=True)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args()
    print(json.dumps(audit(Path(args.out)) if args.audit_only else run(args.config,args.out),indent=2))
