"""Replay an archived store with its recorded extension code and all losses."""
import argparse,hashlib,importlib.util,itertools,json,tarfile,tempfile
from pathlib import Path
from threadpoolctl import threadpool_limits
from recoverml.core import Graph,pack,digest
from recoverml.capability_retention import restricted
from recoverml.witness import WitnessRestorer

def run(evidence,store_name):
    report=json.loads((evidence/'report.json').read_text());expected=report['source_dependencies']['capability_ops.py']
    candidates=[p for p in (evidence.parent/'source_snapshot').glob('*capability_ops.py') if hashlib.sha256(p.read_bytes()).hexdigest()==expected]
    if not candidates:raise ValueError('Recorded replay extension missing')
    spec=importlib.util.spec_from_file_location('recoverml._recorded_capability_ops',candidates[0]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    exact=0
    with tempfile.TemporaryDirectory(prefix='recoverml_saved_replay_') as temporary,threadpool_limits(limits=1):
        root=Path(temporary)
        with tarfile.open(evidence/'stores.tar.gz','r:gz') as archive:archive.extractall(root,filter='data')
        store=root/store_name
        if not (store/'manifest.json').exists():store=root/'stores'/store_name
        if not store.resolve().is_relative_to(root):raise ValueError('Invalid store path')
        g=Graph.read(store/'manifest.json');assert not g.archive
        contract=json.loads((store/'capability_contract.json').read_text());caps=contract['capabilities'];groups=sorted(set(caps.values()))
        for count in range(min(contract['maximum_lost_groups'],len(groups))+1):
            for lost in itertools.combinations(groups,count):
                for version,targets in g.targets.items():
                    r=WitnessRestorer(restricted(g,caps,lost),store,replay_execute=module.execute);values=r.version(version)
                    if not all(digest(pack(v))==g.nodes[t].blob for v,t in zip(values,targets)):raise RuntimeError('Saved target mismatch')
                    if any(e.get('producer') and caps.get(e['producer']) in lost for e in r.trace):raise RuntimeError('Disabled producer used')
                    exact+=1
    return dict(store=store_name,exact_requests=exact,all_allowed_losses_checked=True,capture_archive_absent=True,recorded_replay_sha256=expected)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--store',required=True);a=p.parse_args();print(json.dumps(run(a.evidence,a.store),indent=2))
