"""Byte-level encoding transfer over all 230 frozen conditions, including gaps."""
import argparse
from dataclasses import replace
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import traceback

from threadpoolctl import threadpool_limits
from recoverml.core import Graph,canonical,digest
from recoverml.encoded_store import encode,decode,metadata
from recoverml.capability_retention import retained_bytes,restricted
from recoverml.component_retention import optimize
from recoverml.scenario_retention import optimize as reference
from recoverml.robust_heuristics import select,fault_sets
from recoverml.witness import certificate
from benchmark_planner_efficiency import frozen
from verify_release import Snapshot,evidence_inventory,original_evidence_bytes

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/encoded_storage_transfer_oct26.json'


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def run(group,output):
    config=json.loads(CONFIG.read_bytes());output.mkdir(parents=True,exist_ok=False)
    if group not in config['groups']:raise ValueError('Unknown frozen group')
    sources=sorted((ROOT/'src/recoverml').glob('*.py'))+[Path(__file__).resolve(),
        ROOT/'scripts/benchmark_planner_efficiency.py',ROOT/'scripts/verify_release.py',CONFIG]
    hashes={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in sources}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    dump(output/'run_start.json',dict(commit=commit,group=group,config=config,source_sha256=hashes,timestamp_ns=time.time_ns()))
    with tarfile.open(output/'source_snapshot.tar.gz','w:gz') as archive:
        for path in sources:archive.add(path,arcname=path.relative_to(ROOT))
    inputs={};cases=list(frozen(group,inputs))
    if len(cases)!=config['groups'][group]:raise ValueError('Frozen condition denominator differs')
    payloads={}
    def read_tar(raw,label):
        inputs[label]=digest(raw)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive:
                name=Path(member.name).name
                if member.isfile() and re.fullmatch(r'[0-9a-f]{64}\.pkl',name):
                    content=archive.extractfile(member).read();blob=name[:-4]
                    if digest(content)!=blob:raise ValueError('Original payload identity differs')
                    if blob in payloads and payloads[blob]!=content:raise ValueError('Conflicting original payload')
                    payloads[blob]=content
    if group=='scientific':
        name='results/research/scientific_complete_oct16/captures.tar.gz';read_tar((ROOT/name).read_bytes(),name)
    elif group=='cloud':
        for path in sorted((ROOT/'results/research/strong_baseline_cloud_oct16').glob('seed*/[!v]*/captures.tar.gz')):
            read_tar(path.read_bytes(),path.relative_to(ROOT).as_posix())
    elif group=='retinal':
        name='results/research/eyeai_complete_oct15/stores_deduplicated.tar.gz';snapshot=Snapshot(ROOT,'HEAD')
        expected=evidence_inventory(snapshot)['expected_sha256'][name]
        raw,_=original_evidence_bytes(snapshot,name,expected);read_tar(raw,name)
    else:
        name='results/research/gigabyte_letter_oct16/recovered_frontier_payloads.tar.gz';read_tar((ROOT/name).read_bytes(),name)
    required=set().union(*(g.candidates for _,g,_,_,_ in cases));objects=output/'objects';objects.mkdir()
    def put(raw):
        sha=digest(raw);path=objects/(sha+'.bin')
        if not path.exists():path.write_bytes(raw)
        elif path.read_bytes()!=raw:raise ValueError('Object collision')
        return sha
    inventory={}
    for blob in sorted(required&payloads.keys()):
        raw=payloads[blob];record=dict(raw_bytes=len(raw))
        for policy in config['policies']:
            encoded=encode(raw,policy)
            if decode(encoded,len(raw),blob)!=raw:raise ValueError('Lossless transfer differs')
            record[policy]=dict(object=put(encoded),bytes=len(encoded))
        inventory[blob]=record
    dump(output/'payload_inventory.json',inventory);dump(output/'input_sha256.json',inputs)
    rows=[]
    def measure(graph,caps,k,selected,policy):
        header=metadata(graph,caps,k,policy);header_sha=put(header)
        with tempfile.TemporaryDirectory(prefix='recoverml-encoded-transfer-') as temporary:
            directory=Path(temporary);(directory/'blobs').mkdir();(directory/'metadata.rml').write_bytes(header)
            for blob in selected:shutil.copyfile(objects/(inventory[blob][policy]['object']+'.bin'),directory/'blobs'/(blob+'.pkl'))
            index={p.relative_to(directory).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes()))
                   for p in directory.rglob('*') if p.is_file()}
            return dict(bytes=sum(item['bytes'] for item in index.values()),metadata_object=header_sha,inventory=index,selected=sorted(selected))
    with threadpool_limits(limits=1):
        for case,graph,caps,k,expected in cases:
            raw_selected,status,diag=optimize(graph,caps,k,time_limit_s=config['solver_time_limit_s'])
            if status!='ok' or not diag.get('storage_optimal') or retained_bytes(graph,raw_selected,caps,k)!=expected:
                raise ValueError('Frozen raw optimum changed')
            missing=sorted(graph.candidates-inventory.keys())
            row=dict(case=case,graph_object=put(canonical(graph.manifest())),capabilities=caps,k=k,
                raw_exact_bytes=expected,raw_selected=sorted(raw_selected),missing_candidates=missing,
                missing_selected=sorted(raw_selected-inventory.keys()),methods={})
            if not row['missing_selected']:
                row['methods']['adaptive_raw_choice']=measure(graph,caps,k,raw_selected,'adaptive')
                row['methods']['gzip_raw_choice']=measure(graph,caps,k,raw_selected,'gzip9')
            if missing:
                row['status']='SELECTED_ONLY' if not row['missing_selected'] else 'UNAVAILABLE'
            else:
                views={}
                for policy,method in [('adaptive','adaptive_exact'),('gzip9','gzip_exact')]:
                    view=Graph(env=graph.env);view.targets=graph.targets;view.roots=graph.roots
                    view.nodes={nid:replace(n,size=inventory[n.blob][policy]['bytes']) for nid,n in graph.nodes.items()};views[policy]=view
                    selected,status,diag=optimize(view,caps,k,time_limit_s=config['solver_time_limit_s'])
                    other,other_status,other_diag=reference(view,caps,k,time_limit_s=config['solver_time_limit_s'])
                    if status!='ok' or other_status!='ok' or not diag.get('storage_optimal') or not other_diag.get('storage_optimal') or \
                            sum(view.sizes()[b] for b in selected)!=sum(view.sizes()[b] for b in other):
                        raise ValueError('Encoded exact formulations disagree')
                    row['methods'][method]=measure(graph,caps,k,selected,policy)
                    row['methods'][method]['reference_selected']=sorted(other)
                view=views['adaptive']
                selected,_=select(view,caps,k,retained_bytes(view,view.candidates,caps,k),True)
                row['methods']['adaptive_local']=measure(graph,caps,k,selected,'adaptive')
                targets={graph.nodes[t].blob for ts in graph.targets.values() for t in ts}
                row['methods']['adaptive_snapshots']=measure(graph,caps,k,graph.roots|targets,'adaptive')
                row['status']='COMPLETE'
            for method,item in row['methods'].items():
                selected=set(item['selected'])
                item['certificates']=[dict(disabled=list(lost),certificate=certificate(restricted(graph,caps,lost),selected))
                                      for lost in fault_sets(caps,k)]
                if not all(c['certificate']['complete'] for c in item['certificates']):raise ValueError('Encoded store lost conditional recoverability')
            rows.append(row);dump(output/'conditions.json',rows)
            print(group,case,row['status'],{m:r['bytes'] for m,r in row['methods'].items()},flush=True)
    with tarfile.open(output/'objects.tar.gz','w:gz') as archive:
        for path in sorted(objects.iterdir()):archive.add(path,arcname=path.name)
    changed=[p for p,sha in hashes.items() if digest((ROOT/p).read_bytes())!=sha]
    dump(output/'report.json',dict(status='PASS' if not changed else 'FAIL',group=group,conditions=len(rows),source_changed=changed,
        complete=sum(r['status']=='COMPLETE' for r in rows),selected_only=sum(r['status']=='SELECTED_ONLY' for r in rows),
        unavailable=sum(r['status']=='UNAVAILABLE' for r in rows),original_payloads_roundtripped=len(inventory),
        closed_sha256={p.name:digest(p.read_bytes()) for p in output.iterdir() if p.is_file()},qualification=config['qualification']))
    if changed:raise ValueError('Runtime source changed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--group',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:run(args.group,args.output)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
