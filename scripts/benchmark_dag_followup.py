"""Fresh paired planner timing on all 48 frozen scientific conditions.

No model training or recovery occurs here. Existing raw runtime evidence stays
unchanged. Timing includes applicability checks and proof checking.
"""
import argparse
import gzip
import json
from pathlib import Path
import random
import statistics
import tarfile
import tempfile
import time

from threadpoolctl import threadpool_limits
from recoverml.core import Graph, digest, environment
from recoverml.capability_retention import retained_bytes
from recoverml.component_retention import optimize as exact
from recoverml.dag_retention import network
from recoverml.scenario_retention import optimize as reference
from recoverml.robust_heuristics import select
from recoverml.scientific_workflows import caps_for


def run(output, original):
    output.mkdir(parents=True, exist_ok=False)
    sources = sorted(Path('src/recoverml').glob('*.py')) + [Path(__file__)]
    hashes = {str(p): digest(p.read_bytes()) for p in sources}
    (output / 'protocol.json').write_text(json.dumps(dict(
        purpose='Follow-up timing after engineering change, all 48 original conditions, no case selection',
        workflows=['iris_union', 'digits_pca', 'diabetes_poly', 'digits_forest'], seeds=[101, 211],
        scopes=['preprocessing', 'broad'], k=[0,1,2], repetitions=5,
        methods=['RecoverML_auto', 'scenario_exact', 'robust_local'],
        timing_scope='Full callable including applicability and proof checks; randomized repeated method order; shared host descriptive timings',
        metadata_only=True, payload_recovery_rerun=False), indent=2)+'\n')
    records = json.loads(gzip.decompress((original / 'planner_records.json.gz').read_bytes()))
    expected = {r['case']: r['actual_bytes'] for r in records
                if r['policy']=='RecoverML_exact' and 'budget_fraction' not in r}
    archive_hash = digest((original / 'captures.tar.gz').read_bytes())
    rows = []; calls = []
    start_receipt = dict(timestamp_ns=time.time_ns(), source_sha256=hashes, environment=environment(),
                         capture_archive_sha256=archive_hash)
    (output/'run_start.json').write_text(json.dumps(start_receipt, indent=2)+'\n')
    with tempfile.TemporaryDirectory() as temp, threadpool_limits(limits=1):
        with tarfile.open(original / 'captures.tar.gz') as archive:
            # Extract only manifests and retain exact original metadata bytes.
            for member in archive.getmembers():
                if member.isfile() and member.name.endswith('/manifest.json'):
                    archive.extract(member, path=temp, filter='data')
        manifests = sorted(Path(temp).rglob('manifest.json'))
        if len(manifests)!=8: raise RuntimeError('Expected all eight captures')
        for manifest in manifests:
            graph=Graph.read(manifest); history=manifest.parent.name
            for scope in ('preprocessing', 'broad'):
                caps=caps_for(graph,scope)
                for k in (0,1,2):
                    case=f'{history}-{scope}-k{k}'
                    budget=retained_bytes(graph,graph.candidates,caps,k)
                    eligible=network(graph,caps,k)[0] is not None
                    timing={m:[] for m in ('RecoverML_auto','scenario_exact','robust_local')}
                    sizes={}; diags={}
                    for repeat in range(5):
                        order=list(timing);random.Random(case+str(repeat)).shuffle(order)
                        for method in order:
                            start=time.perf_counter()
                            if method=='robust_local':
                                selected,diag=select(graph,caps,k,budget,True); status='heuristic'
                            else:
                                selected,status,diag=(exact if method=='RecoverML_auto' else reference)(graph,caps,k)
                            elapsed=time.perf_counter()-start
                            size=retained_bytes(graph,selected,caps,k)
                            if method!='robust_local' and (status!='ok' or size!=expected[case] or not diag['storage_optimal']):
                                raise RuntimeError('Exact result disagrees with frozen original optimum')
                            if not diag['robust_certified']: raise RuntimeError('Returned store is not robust')
                            timing[method].append(elapsed);sizes[method]=size;diags[method]=diag
                            calls.append(dict(case=case,method=method,repetition=repeat,planning_s=elapsed,
                                timestamp_ns=time.time_ns(),retained_bytes=size,status=status,diagnostic=diag))
                    rows.append(dict(case=case,dag_eligible=eligible,original_minimum=expected[case],sizes=sizes,
                        median_s={m:statistics.median(v) for m,v in timing.items()},
                        speedup_vs_local=statistics.median(timing['robust_local'])/statistics.median(timing['RecoverML_auto']),
                        speedup_vs_scenario=statistics.median(timing['scenario_exact'])/statistics.median(timing['RecoverML_auto'])))
                    print(case, 'eligible', eligible, 'seconds', rows[-1]['median_s'], flush=True)
    with gzip.open(output/'planner_calls.json.gz','wt') as handle:json.dump(calls,handle)
    changed=[str(p) for p in sources if digest(p.read_bytes())!=hashes[str(p)]]
    (output/'report.json').write_text(json.dumps(dict(status='PASS' if not changed else 'FAIL',
        conditions=len(rows),calls=len(calls),source_changed=changed,results=rows,
        all_exact_equal_original=all(r['sizes']['RecoverML_auto']==r['original_minimum'] for r in rows),
        qualification='Metadata-only paired follow-up on existing constructed histories; no new payload recovery or published-system native run'),indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--original',type=Path,default=Path('results/research/scientific_complete_oct16'))
    args=parser.parse_args();run(args.output,args.original)
