"""Lossless persistent storage with unchanged canonical artifact identities.

Encoding changes byte costs, so selection uses an explicit cost-only graph view.
Replay always uses the original graph and hashes. Compression is standard zlib/
XZ machinery, available equally to comparator policies; it is not a new optimizer.
"""
from dataclasses import replace
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import zlib

from .core import Graph, Node, RestoreError, canonical, digest, pack
from .capability_retention import contract, restricted, validate

MAGIC=b'RECOVERML-ENCODED-1\n'
POLICIES={'identity','gzip9','adaptive'}
MAX_METADATA=64*1024*1024


def shuffle(raw):
    """Standard byte-shuffle idea, with a fixed eight-byte lane and exact tail."""
    stop=len(raw)//8*8
    return b''.join(raw[i:stop:8] for i in range(8))+raw[stop:]


def unshuffle(raw):
    count=len(raw)//8;stop=count*8;result=bytearray(len(raw))
    for i in range(8):result[i:stop:8]=raw[i*count:(i+1)*count]
    result[stop:]=raw[stop:]
    return bytes(result)


def variants(raw,policy):
    if policy not in POLICIES:raise ValueError('Unknown encoding policy')
    if policy=='identity':return [b'\0'+raw]
    shuffled=shuffle(raw)
    choices=[b'\3'+gzip.compress(raw,compresslevel=9,mtime=0),
             b'\6'+gzip.compress(shuffled,compresslevel=9,mtime=0)]
    if policy=='adaptive':
        choices.extend([b'\0'+raw,b'\1'+zlib.compress(raw,9),
            b'\2'+lzma.compress(raw,format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=6),
            b'\4'+zlib.compress(shuffled,9),
            b'\5'+lzma.compress(shuffled,format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=6)])
    return choices


def encode(raw,policy='adaptive'):
    return min(variants(raw,policy),key=lambda value:(len(value),value[0]))


def decode(encoded,size,identity):
    if type(size) is not int or size<0 or not encoded:
        raise RestoreError('Invalid encoded size or empty payload')
    mode,data=encoded[0],encoded[1:]
    try:
        if mode==0:raw=data
        elif mode in (1,3,4,6):
            decoder=zlib.decompressobj(zlib.MAX_WBITS if mode in (1,4) else 31)
            raw=decoder.decompress(data,size+1)
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise RestoreError('Truncated, oversized or trailing compressed payload')
        elif mode in (2,5):
            decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=128*1024*1024)
            raw=decoder.decompress(data,max_length=size+1)
            if not decoder.eof or decoder.unused_data:
                raise RestoreError('Truncated, oversized or trailing XZ payload')
        else:raise RestoreError('Unknown encoded payload mode')
    except (zlib.error,lzma.LZMAError,EOFError) as exc:
        raise RestoreError('Invalid compressed artifact') from exc
    if mode in (4,5,6):raw=unshuffle(raw)
    if len(raw)!=size or digest(raw)!=identity:
        raise RestoreError('Decoded artifact size or SHA-256 mismatch')
    return raw


def metadata(graph,capabilities,k,policy):
    validate(graph,capabilities,k)
    if policy not in POLICIES:raise ValueError('Unknown encoding policy')
    raw=canonical(dict(schema=1,format='lossless-per-file-v1',graph=graph.manifest(),
                       contract=json.loads(contract(capabilities,k))))
    if len(raw)>MAX_METADATA:raise ValueError('Encoded metadata limit exceeded')
    return MAGIC+len(raw).to_bytes(8,'big')+hashlib.sha256(raw).digest()+zlib.compress(raw,9)


class Representation:
    """Capture-time encoding inventory; never passed to a recovery request."""
    def __init__(self,graph,payloads=None,policy='adaptive'):
        self.graph,self.policy=graph,policy
        payloads=graph.archive if payloads is None else payloads
        self.encoded={}
        sizes=graph.sizes()
        for blob in sorted(graph.candidates):
            raw=payloads[blob]
            if digest(raw)!=blob or len(raw)!=sizes[blob]:raise ValueError('Capture payload differs')
            encoded=encode(raw,policy)
            if decode(encoded,len(raw),blob)!=raw:raise ValueError('Encoder round-trip differs')
            self.encoded[blob]=encoded
        # IDs, hashes and reachability remain unchanged. Only paid byte costs differ.
        self.cost_graph=Graph(env=graph.env)
        self.cost_graph.nodes={nid:replace(n,size=len(self.encoded[n.blob])) for nid,n in graph.nodes.items()}
        self.cost_graph.targets={v:list(ts) for v,ts in graph.targets.items()}
        self.cost_graph.roots=set(graph.roots)

    def size(self,selected,capabilities,k):
        if not set(selected)<=self.graph.candidates:raise ValueError('Unknown selected artifact')
        return len(metadata(self.graph,capabilities,k,self.policy))+sum(len(self.encoded[b]) for b in selected)

    def write(self,selected,capabilities,k,destination):
        selected=set(selected);destination=Path(destination)
        if not self.graph.roots<=selected<=self.graph.candidates:raise ValueError('Invalid selected set or missing mandatory roots')
        header=metadata(self.graph,capabilities,k,self.policy)
        destination.mkdir(parents=True,exist_ok=False)
        (destination/'blobs').mkdir()
        (destination/'metadata.rml').write_bytes(header)
        for blob in sorted(selected):(destination/'blobs'/(blob+'.pkl')).write_bytes(self.encoded[blob])
        actual=sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
        if actual!=self.size(selected,capabilities,k):raise RuntimeError('Encoded physical byte accounting differs')
        return actual


class _DecodedPath:
    """Read-only path view used only by the existing checked witness executor.

    scandir observes actual retained filenames. read_bytes decodes the selected
    payload on demand; no plaintext mirror or capture archive is created.
    """
    def __init__(self,store,path):self.store,self.path=store,path
    def __fspath__(self):return os.fspath(self.path)
    def __truediv__(self,part):return _DecodedPath(self.store,self.path/part)
    def read_bytes(self):
        if self.path.parent!=self.store.path/'blobs' or self.path.suffix!='.pkl':
            raise RestoreError('Unexpected encoded witness path')
        return self.store.load(self.path.stem)


def parse_metadata(encoded):
    if not encoded.startswith(MAGIC) or len(encoded)<len(MAGIC)+40:
        raise RestoreError('Unsupported encoded metadata header')
    offset=len(MAGIC);size=int.from_bytes(encoded[offset:offset+8],'big')
    if size>MAX_METADATA:raise RestoreError('Encoded metadata exceeds size limit')
    raw=decode(b'\1'+encoded[offset+40:],size,encoded[offset+8:offset+40].hex())
    return json.loads(raw)


class EncodedStore:
    FORMAT='lossless-per-file-v1'
    def __init__(self,path):
        self.path=Path(path).resolve()
        if (self.path/'metadata.rml').is_symlink():raise RestoreError('Encoded metadata must be a regular retained file')
        record=parse_metadata((self.path/'metadata.rml').read_bytes())
        if record['schema']!=1 or record['format']!=self.FORMAT or record['graph']['schema']!=1:
            raise RestoreError('Unsupported encoded store schema or policy')
        m=record['graph'];self.graph=Graph(env=m['environment'])
        self.graph.nodes={n['id']:Node(**n) for n in m['nodes']}
        if len(self.graph.nodes)!=len(m['nodes']):raise RestoreError('Duplicate graph node')
        self.graph.targets=m['targets'];self.graph.roots=set(m['mandatory_blobs'])
        sizes={}
        for node in self.graph.nodes.values():
            if re.fullmatch(r'[0-9a-f]{64}',node.blob) is None or type(node.size) is not int or node.size<0:
                raise RestoreError('Invalid canonical artifact identity')
            if node.blob in sizes and sizes[node.blob]!=node.size:raise RestoreError('Conflicting artifact sizes')
            sizes[node.blob]=node.size
            if not set(node.deps)<=self.graph.nodes.keys():raise RestoreError('Unknown graph dependency')
        if not self.graph.roots<=sizes.keys():raise RestoreError('Unknown mandatory root')
        self.sizes=sizes;self.contract=record['contract']
        validate(self.graph,self.contract['capabilities'],self.contract['maximum_lost_groups'])
        self.protected={n for ts in self.graph.targets.values() for n in ts}
        if not self.protected<=self.graph.nodes.keys():raise RestoreError('Unknown protected target')
        files=list((self.path/'blobs').glob('*.pkl'))
        if any(p.is_symlink() for p in files):raise RestoreError('Encoded retained files cannot be symlinks')
        self.retained={p.stem for p in files if p.is_file() and p.stem in sizes}
        if not self.graph.roots<=self.retained:raise RestoreError('Missing encoded mandatory root')

    def load(self,blob):
        if blob not in self.retained:raise RestoreError('Encoded artifact is not retained')
        try:encoded=(self.path/'blobs'/(blob+'.pkl')).read_bytes()
        except OSError as exc:raise RestoreError('Cannot read encoded retained artifact') from exc
        return decode(encoded,self.sizes[blob],blob)

    def recover(self,output,*,target_ids=None,disabled=(),replay_execute=None,verify_environment=True):
        output=Path(output).resolve()
        if output.is_relative_to(self.path) or self.path.is_relative_to(output):
            raise ValueError('Choose output outside the persistent encoded store')
        requested=sorted(self.protected) if target_ids is None else list(dict.fromkeys(target_ids))
        if not requested or not set(requested)<=self.protected:raise ValueError('Request must contain protected target nodes')
        # Validate disabled group names even when all requested files are retained.
        view=restricted(self.graph,self.contract['capabilities'],disabled)
        view.targets={'request':requested}
        targets={self.graph.nodes[n].blob for n in requested}
        for blob in targets:
            path=output/(blob+'.pkl')
            if path.exists() and (path.stat().st_size!=self.sizes[blob] or digest(path.read_bytes())!=blob):
                raise RestoreError('Existing requested output differs')
        restorer=None
        if not targets<=self.retained:
            from .witness import WitnessRestorer
            restorer=WitnessRestorer(view,_DecodedPath(self,self.path),verify_environment=verify_environment,
                                     replay_execute=replay_execute)
        output.mkdir(parents=True,exist_ok=True)
        for target in requested:
            blob=self.graph.nodes[target].blob
            raw=self.load(blob) if blob in self.retained else pack(restorer.get(target))
            if len(raw)!=self.sizes[blob] or digest(raw)!=blob:raise RestoreError('Recovered canonical target differs')
            (output/(blob+'.pkl')).write_bytes(raw)
        hashes={b:digest((output/(b+'.pkl')).read_bytes()) for b in targets}
        if any(b!=sha for b,sha in hashes.items()):raise RestoreError('Final target verification failed')
        return dict(status='PASS',mode='encoded_export' if restorer is None else 'encoded_replay',
                    target_sha256=hashes,operations=[] if restorer is None else restorer.trace,
                    qualification='Original canonical artifact bytes; persistent encoding does not change target identity.')


def main():
    import argparse
    import importlib
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('create',help='Select and encode a complete raw capture')
    create.add_argument('--capture',type=Path,required=True);create.add_argument('--contract',type=Path,required=True)
    create.add_argument('--output',type=Path,required=True);create.add_argument('--policy',choices=sorted(POLICIES),default='adaptive')
    recover=commands.add_parser('recover',help='Restore original canonical target files')
    recover.add_argument('--store',type=Path,required=True);recover.add_argument('--output',type=Path,required=True)
    recover.add_argument('--target',action='append');recover.add_argument('--disable',action='append',default=[])
    families={'base':'operators','capability':'capability_ops','census':'broad_workflows',
              'scientific':'scientific_workflows','multiview':'multiview_workflow','retinal':'eyeai_workflow'}
    recover.add_argument('--operators',choices=sorted(families),default='base')
    args=parser.parse_args()
    if args.command=='create':
        from .component_retention import optimize
        graph=Graph.read(args.capture/'manifest.json')
        payloads={b:(args.capture/'blobs'/(b+'.pkl')).read_bytes() for b in graph.candidates}
        declared=json.loads(args.contract.read_bytes());caps=declared['capabilities'];k=declared['maximum_lost_groups']
        representation=Representation(graph,payloads,args.policy)
        selected,status,diag=optimize(representation.cost_graph,caps,k)
        if status!='ok' or not diag.get('storage_optimal') or not diag.get('robust_certified'):
            raise RestoreError('No certified encoded optimum was obtained')
        size=representation.write(selected,caps,k,args.output)
        result=dict(status='PASS',store_bytes=size,selected=sorted(selected),storage_optimal=True,
                    qualification='Optimum for the declared per-file encoding costs; original canonical identities unchanged.')
    else:
        def execute(op,values,parameters):
            module=importlib.import_module('recoverml.'+families[args.operators])
            return module.execute(op,values,parameters)
        result=EncodedStore(args.store).recover(args.output,target_ids=args.target,disabled=args.disable,replay_execute=execute)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
