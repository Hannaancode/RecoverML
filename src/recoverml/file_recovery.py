"""Demand-driven exact target-file recovery with retained-file export first."""
import json
from pathlib import Path
import time
from .core import RestoreError, digest, pack
from .file_export import export_retained_targets


def recover_requested_files(store, output, *, target_ids, disabled=(), replay_execute=None,
                            verify_environment=True):
    started=time.perf_counter()
    exported=export_retained_targets(store,output,target_ids=target_ids)
    if exported is not None:
        return exported
    from .core import Graph
    from .capability_retention import restricted
    from .witness import WitnessRestorer
    store,output=Path(store),Path(output)
    graph=Graph.read(store/'manifest.json')
    contract=json.loads((store/'capability_contract.json').read_bytes())
    view=restricted(graph,contract['capabilities'],disabled)
    view.targets={'request':list(target_ids)}
    restorer=WitnessRestorer(view,store,replay_execute=replay_execute,
                             verify_environment=verify_environment)
    output.mkdir(parents=True,exist_ok=True)
    for target in target_ids:
        blob=graph.nodes[target].blob;path=output/(blob+'.pkl')
        if path.exists() and digest(path.read_bytes())!=blob:
            raise RestoreError('Existing requested output differs')
    for target in target_ids:
        blob=graph.nodes[target].blob
        source=store/'blobs'/(blob+'.pkl')
        if source.is_file():
            export_retained_targets(store,output,target_ids=[target])
        else:
            raw=pack(restorer.get(target))
            if digest(raw)!=blob:raise RestoreError('Requested target differs')
            (output/(blob+'.pkl')).write_bytes(raw)
    identities={graph.nodes[t].blob for t in target_ids}
    hashes={b:digest((output/(b+'.pkl')).read_bytes()) for b in identities}
    if any(k!=v for k,v in hashes.items()):raise RestoreError('Requested output verification failed')
    return dict(status='PASS',mode='requested_replay',target_sha256=hashes,operations=restorer.trace,
                core_elapsed_s=time.perf_counter()-started)
