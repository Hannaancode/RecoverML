"""Exact prefix/suffix deltas and coupled retention of their required bases.

These are standard lossless delta/compression operations, not a new codec or
optimizer. The cost graph distinguishes storage decoding from ML replay so a
delta can never depend on an unretained, replay-only base. Canonical identities,
the original graph and environment checks remain unchanged.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import zlib

from .core import Graph,Node,RestoreError,canonical,digest
from .capability_retention import contract,validate
from .encoded_store import Representation,EncodedStore,MAGIC,MAX_METADATA,encode,decode,parse_metadata

FORMAT='lossless-prefix-delta-v1'
DELTA=7
HEADER=89  # tag, base SHA, prefix, suffix, middle size, middle SHA
MIN_OVERLAP=128


def overlap(a,b):
    """Longest equal prefix, then a nonoverlapping equal suffix."""
    lo,hi=0,min(len(a),len(b))
    while lo<hi:
        mid=(lo+hi+1)//2
        if a[:mid]==b[:mid]:lo=mid
        else:hi=mid-1
    prefix=lo;lo,hi=0,min(len(a),len(b))-prefix
    while lo<hi:
        mid=(lo+hi+1)//2
        if a[-mid:]==b[-mid:]:lo=mid
        else:hi=mid-1
    return prefix,lo


def delta(base_blob,base,target):
    prefix,suffix=overlap(base,target)
    middle=target[prefix:len(target)-suffix if suffix else len(target)]
    return (bytes([DELTA])+bytes.fromhex(base_blob)+prefix.to_bytes(8,'big')+
            suffix.to_bytes(8,'big')+len(middle).to_bytes(8,'big')+
            hashlib.sha256(middle).digest()+encode(middle))


def descriptor(encoded,size):
    if len(encoded)<=HEADER or encoded[0]!=DELTA or encoded[HEADER]>6:
        raise RestoreError('Invalid delta payload header or nested encoding')
    base=encoded[1:33].hex()
    prefix=int.from_bytes(encoded[33:41],'big');suffix=int.from_bytes(encoded[41:49],'big')
    middle_size=int.from_bytes(encoded[49:57],'big')
    if prefix+suffix+middle_size!=size:raise RestoreError('Delta lengths do not match canonical size')
    return base,prefix,suffix,middle_size,encoded[57:89].hex()


def metadata(graph,caps,k):
    validate(graph,caps,k)
    raw=canonical(dict(schema=1,format=FORMAT,graph=graph.manifest(),contract=json.loads(contract(caps,k))))
    if len(raw)>MAX_METADATA:raise ValueError('Delta metadata limit exceeded')
    return MAGIC+len(raw).to_bytes(8,'big')+hashlib.sha256(raw).digest()+zlib.compress(raw,9)


class DeltaRepresentation:
    """One deterministic base option per artifact plus its full-file option.

    Candidates are ordered by (canonical size, SHA). A non-root artifact's base
    maximizes equal prefix+suffix among earlier candidates, with SHA tie break.
    Keep that option only when its complete encoded file is smaller. Optimality
    is relative to this declared candidate inventory, not all possible deltas.
    """
    def __init__(self,graph,payloads=None,full_encoded=None):
        self.graph=graph;payloads=graph.archive if payloads is None else payloads
        sizes=graph.sizes()
        if any(digest(payloads[b])!=b or len(payloads[b])!=sizes[b] for b in graph.candidates):
            raise ValueError('Capture payload differs')
        if full_encoded is None:full_encoded=Representation(graph,payloads).encoded
        if set(full_encoded)!=graph.candidates:raise ValueError('Full encoding inventory differs')
        for b,encoded in full_encoded.items():decode(encoded,sizes[b],b)
        self.full=dict(full_encoded);self.deltas={};self.bases={};previous=[]
        for blob in sorted(graph.candidates,key=lambda b:(sizes[b],b)):
            if blob not in graph.roots:
                choices=[]
                for base in previous:
                    prefix,suffix=overlap(payloads[base],payloads[blob])
                    if prefix+suffix>=MIN_OVERLAP:choices.append((-(prefix+suffix),base))
                if choices:
                    base=min(choices)[1];encoded=delta(base,payloads[base],payloads[blob])
                    if len(encoded)<len(self.full[blob]):
                        self.deltas[blob]=encoded;self.bases[blob]=base
            previous.append(blob)
        self._cost_graph()

    def _cost_graph(self):
        graph=self.graph
        # Retaining all full files is feasible and strictly cheaper than any
        # virtual node. Thus a certified minimum cannot select a virtual node.
        self.prohibitive=1+sum(len(v) for v in self.full.values())
        view=Graph(env=graph.env)
        view.nodes={nid:replace(n,size=self.prohibitive) for nid,n in graph.nodes.items()}
        view.targets={v:list(ts) for v,ts in graph.targets.items()}
        self.physical={};self.full_tokens={};self.delta_tokens={}
        def key(label,blob):return digest(('recoverml-delta-cost-v1:'+label+':'+blob).encode())
        def add(label,blob,deps,physical=None):
            nid=key(label,blob)
            if nid in view.nodes:raise ValueError('Cost graph node collision')
            identity=physical if physical is not None else key('materialized',blob)
            if label=='bridge':identity=blob
            size=len(self.physical[physical][1]) if physical is not None else self.prohibitive
            view.nodes[nid]=Node(nid,label,list(deps),{},physical is None,'storage',identity,size,0.,0)
            return nid
        for blob in sorted(graph.candidates):
            token=digest(self.full[blob]);self.physical[token]=(blob,self.full[blob]);self.full_tokens[blob]=token
            full=add('full',blob,[],token)
            materialized=add('decode_full',blob,[full])
            add('bridge',blob,[materialized])
        for blob in sorted(self.deltas):
            token=digest(self.deltas[blob]);self.physical[token]=(blob,self.deltas[blob]);self.delta_tokens[blob]=token
            paid=add('delta',blob,[],token)
            add('decode_delta',blob,[paid,key('decode_full',self.bases[blob])])
        view.roots={self.full_tokens[b] for b in graph.roots}
        virtual=view.candidates-self.physical.keys()
        if virtual&self.physical.keys() or len(virtual)!=2*len(graph.candidates):
            raise ValueError('Cost graph artifact collision')
        self.cost_graph=view

    def choices(self,canonical_selected):
        selected=set(canonical_selected)
        if not self.graph.roots<=selected<=self.graph.candidates:raise ValueError('Invalid canonical selection')
        return {self.delta_tokens[b] if b in self.bases and self.bases[b] in selected else self.full_tokens[b] for b in selected}

    def files(self,tokens):
        tokens=set(tokens)
        if not self.cost_graph.roots<=tokens<=self.physical.keys():raise ValueError('Invalid physical selection')
        files={self.physical[t][0]:self.physical[t][1] for t in tokens}
        if len(files)!=len(tokens):raise ValueError('Both full and delta selected for one artifact')
        for blob,encoded in files.items():
            if encoded[0]==DELTA and descriptor(encoded,self.graph.sizes()[blob])[0] not in files:
                raise ValueError('Selected delta is missing its retained base')
        return files

    def size(self,tokens,caps,k):
        return len(metadata(self.graph,caps,k))+sum(map(len,self.files(tokens).values()))

    def write(self,tokens,caps,k,destination):
        files=self.files(tokens);header=metadata(self.graph,caps,k);destination=Path(destination)
        destination.mkdir(parents=True,exist_ok=False);(destination/'blobs').mkdir()
        (destination/'metadata.rml').write_bytes(header)
        for blob,encoded in sorted(files.items()):(destination/'blobs'/(blob+'.pkl')).write_bytes(encoded)
        actual=sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
        if actual!=len(header)+sum(map(len,files.values())):raise RuntimeError('Delta physical byte accounting differs')
        return actual


class DeltaStore(EncodedStore):
    FORMAT=FORMAT

    def __init__(self,path):
        super().__init__(path)
        for blob in self.graph.roots:
            with (self.path/'blobs'/(blob+'.pkl')).open('rb') as stream:tag=stream.read(1)
            if not tag or tag[0]>6:raise RestoreError('Mandatory roots must have a full encoding')

    def load(self,blob):
        if blob not in self.retained:raise RestoreError('Delta artifact is not retained')
        current=blob;pending=[];seen=set()
        while True:
            if current not in self.retained:raise RestoreError('Missing retained delta base')
            if current in seen:raise RestoreError('Cyclic delta dependency')
            seen.add(current)
            try:encoded=(self.path/'blobs'/(current+'.pkl')).read_bytes()
            except OSError as exc:raise RestoreError('Cannot read retained delta artifact') from exc
            if not encoded or encoded[0]!=DELTA:
                raw=decode(encoded,self.sizes[current],current);break
            base,prefix,suffix,middle_size,middle_sha=descriptor(encoded,self.sizes[current])
            if base not in self.sizes or (self.sizes[base],base)>=(self.sizes[current],current):
                raise RestoreError('Delta base violates the acyclic canonical order')
            if prefix+suffix>self.sizes[base]:raise RestoreError('Delta copy exceeds base size')
            middle=decode(encoded[HEADER:],middle_size,middle_sha)
            pending.append((current,prefix,suffix,middle));current=base
        for target,prefix,suffix,middle in reversed(pending):
            raw=raw[:prefix]+middle+(raw[-suffix:] if suffix else b'')
            if len(raw)!=self.sizes[target] or digest(raw)!=target:raise RestoreError('Reconstructed delta artifact differs')
        return raw


def open_store(path):
    if (Path(path)/'metadata.rml').is_symlink():raise RestoreError('Metadata must be a regular retained file')
    record=parse_metadata((Path(path)/'metadata.rml').read_bytes())
    return DeltaStore(path) if record['format']==FORMAT else EncodedStore(path)


def main():
    import argparse,importlib
    from .component_retention import optimize
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('create');create.add_argument('--capture',type=Path,required=True)
    create.add_argument('--contract',type=Path,required=True);create.add_argument('--output',type=Path,required=True)
    restore=commands.add_parser('recover');restore.add_argument('--store',type=Path,required=True)
    restore.add_argument('--output',type=Path,required=True);restore.add_argument('--target',action='append')
    restore.add_argument('--disable',action='append',default=[])
    families={'base':'operators','capability':'capability_ops','census':'broad_workflows','scientific':'scientific_workflows','multiview':'multiview_workflow','retinal':'eyeai_workflow'}
    restore.add_argument('--operators',choices=sorted(families),default='base');args=parser.parse_args()
    if args.command=='create':
        graph=Graph.read(args.capture/'manifest.json');payloads={b:(args.capture/'blobs'/(b+'.pkl')).read_bytes() for b in graph.candidates}
        declared=json.loads(args.contract.read_bytes());caps=declared['capabilities'];k=declared['maximum_lost_groups']
        flat=Representation(graph,payloads);coupled=DeltaRepresentation(graph,payloads,flat.encoded);options=[]
        for name,representation in [('flat',flat),('delta',coupled)]:
            selected,status,diag=optimize(representation.cost_graph,caps,k)
            if status!='ok' or not diag.get('storage_optimal') or not diag.get('robust_certified'):
                raise RestoreError('No certified optimum for '+name)
            options.append((representation.size(selected,caps,k),name,representation,selected))
        size,name,representation,selected=min(options,key=lambda o:(o[0],o[1]))
        representation.write(selected,caps,k,args.output)
        result=dict(status='PASS',format=name,store_bytes=size,qualification='Certified optimum within the declared full-file and one-base delta inventory; also compared with the original flat format.')
    else:
        def execute(op,values,params):return importlib.import_module('recoverml.'+families[args.operators]).execute(op,values,params)
        result=open_store(args.store).recover(args.output,target_ids=args.target,disabled=args.disable,replay_execute=execute)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
