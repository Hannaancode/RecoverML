import argparse
import json
from pathlib import Path
from threadpoolctl import threadpool_limits
from .core import Graph, DiskRestorer, RestoreError, canonical, pack, write_store
from .policies import select


def main():
    p = argparse.ArgumentParser(description='Restricted recoverability-preserving ML history prototype')
    sub = p.add_subparsers(dest='command',required=True)
    b = sub.add_parser('benchmark')
    b.add_argument('--config',type=Path,default=Path('configs/preliminary.json'))
    b.add_argument('--out',type=Path,required=True)
    b.add_argument('--keep-stores',action='store_true')
    b.add_argument('--resume',action='store_true')
    a = sub.add_parser('analyze')
    a.add_argument('directory',type=Path)
    r = sub.add_parser('restore')
    r.add_argument('store',type=Path)
    r.add_argument('--version',required=True)
    r.add_argument('--out',type=Path,required=True)
    c = sub.add_parser('select')
    c.add_argument('capture',type=Path)
    c.add_argument('--budget-bytes',type=int,required=True)
    c.add_argument('--policy',default='recoverability_v2')
    c.add_argument('--out',type=Path,required=True)
    args = p.parse_args()
    if args.command == 'benchmark':
        from .benchmark import run
        run(args.config,args.out,args.keep_stores,args.resume)
    elif args.command == 'analyze':
        from .analysis import analyze
        analyze(args.directory)
    elif args.command == 'restore':
        with threadpool_limits(limits=1):
            g = Graph.read(args.store/'manifest.json')
            restorer = DiskRestorer(g,args.store)
            values = restorer.version(args.version)
            args.out.mkdir(parents=True,exist_ok=False)
            for i,value in enumerate(values):
                (args.out/f'target{i}.pkl').write_bytes(pack(value))
            (args.out/'trace.json').write_bytes(canonical(restorer.trace))
        print('All requested target artifact hashes matched.')
    else:
        with threadpool_limits(limits=1):
            g = Graph.read(args.capture/'manifest.json')
            # Planning uses metadata only. Payload bytes are opened AFTER selection.
            selected = select(g,args.policy,args.budget_bytes)
            if selected.status != 'ok' or not g.coverage(selected.retained)[0]:
                raise RestoreError(f'Cannot commit selection: {selected.status}; '
                                   f'coverage={g.coverage(selected.retained)[0]}')
            for blob in selected.retained:
                g.archive[blob]=(args.capture/'blobs'/(blob+'.pkl')).read_bytes()
            write_store(g,selected.retained,args.out)
            (args.out/'certificate.json').write_bytes(canonical(g.certificate(selected.retained)))
        print(json.dumps(dict(status='ok',retained_bytes=g.size(selected.retained),
                              planning_s=selected.planning_s)))
