"""Independent direct executor control and production RecoverML file API."""
import argparse
import json
from pathlib import Path
import time
from recoverml.core import RestoreError, digest
from recoverml.file_export import export_retained_targets
from recoverml.file_recovery import recover_requested_files


def recover(engine, workspace):
    workspace=Path(workspace)
    request=json.loads((workspace/'request.json').read_bytes())
    ids=request['targets'];lost=request['disabled']
    if engine=='RecoverML':
        def execute(op,values,p):
            from recoverml.broad_workflows import execute as replay
            if (op=='census_preprocess' and 'preprocessing' in lost) or op in lost:
                raise RestoreError('Disabled census operator dispatched')
            return replay(op,values,p)
        return recover_requested_files(workspace,workspace/'outputs',target_ids=ids,disabled=lost,replay_execute=execute)
    started=time.perf_counter()
    exported=export_retained_targets(workspace,workspace/'outputs',target_ids=ids)
    if exported is not None:return exported
    from recoverml.core import Graph,DiskRestorer,pack,unpack
    from recoverml.broad_workflows import execute
    graph=Graph.read(workspace/'manifest.json')
    DiskRestorer(graph,workspace)
    contract=json.loads((workspace/'capability_contract.json').read_bytes())
    memo={};operations=[]
    def direct(nid):
        node=graph.nodes[nid]
        if node.blob in memo:return memo[node.blob]
        path=workspace/'blobs'/(node.blob+'.pkl')
        if path.is_file():
            raw=path.read_bytes()
            if digest(raw)!=node.blob:raise RestoreError('Direct retained hash differs')
            value=unpack(raw);action='load'
        else:
            if not node.replayable or contract['capabilities'].get(nid) in lost:
                raise RestoreError('Direct disabled producer or missing input')
            value=execute(node.op,[direct(d) for d in node.deps],node.params)
            raw=pack(value);action='replay'
            if digest(raw)!=node.blob:raise RestoreError('Direct replay hash differs')
        memo[node.blob]=value
        operations.append(dict(node=nid,blob=node.blob,action=action))
        return value
    output=workspace/'outputs';output.mkdir(exist_ok=True)
    for nid in ids:
        raw=pack(direct(nid));blob=graph.nodes[nid].blob
        if digest(raw)!=blob:raise RestoreError('Direct target differs')
        (output/(blob+'.pkl')).write_bytes(raw)
    hashes={graph.nodes[t].blob:digest((output/(graph.nodes[t].blob+'.pkl')).read_bytes()) for t in ids}
    if any(k!=v for k,v in hashes.items()):raise RestoreError('Direct output differs')
    return dict(status='PASS',mode='direct_replay',target_sha256=hashes,operations=operations,
                core_elapsed_s=time.perf_counter()-started)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',choices=['RecoverML','direct_control'],required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    result=recover(args.engine,args.workspace)
    args.receipt.write_text(json.dumps(result,indent=2)+'\n')
