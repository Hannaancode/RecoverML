"""Exact joint compression of an explicitly selected canonical retained set.

This is a storage layout, not a globally optimal joint-compression selector.
Opening an archive decodes the complete retained set in memory. Replay uses a
temporary identity-encoded store; neither memory nor scratch space is free.
"""
import json
from pathlib import Path
import re
import tempfile

from .core import RestoreError,canonical,digest
from .encoded_store import EncodedStore,encode,decode,metadata,parse_metadata,MAX_METADATA

MAGIC=b'RMLSOLID1\n'
MAX_SOLID_BYTES=2*1024*1024*1024


def container(entries):
    index=canonical([[name,len(data),digest(data)] for name,data in entries])
    payload=len(index).to_bytes(8,'big')+index+b''.join(data for _,data in entries)
    if len(index)>MAX_METADATA or len(payload)>MAX_SOLID_BYTES:
        raise ValueError('Solid archive exceeds supported decoded size')
    encoded=encode(payload)
    if decode(encoded,len(payload),digest(payload))!=payload:
        raise RestoreError('Solid encoder roundtrip differs')
    return MAGIC+len(payload).to_bytes(8,'big')+bytes.fromhex(digest(payload))+encoded


def unpack(encoded):
    header=len(MAGIC)+40
    if not encoded.startswith(MAGIC) or len(encoded)<=header:
        raise RestoreError('Invalid solid archive header')
    size=int.from_bytes(encoded[len(MAGIC):len(MAGIC)+8],'big')
    if size<8 or size>MAX_SOLID_BYTES:
        raise RestoreError('Solid decoded size exceeds supported bounds')
    payload=decode(encoded[header:],size,encoded[len(MAGIC)+8:header].hex())
    index_size=int.from_bytes(payload[:8],'big')
    if index_size>MAX_METADATA or index_size>len(payload)-8:
        raise RestoreError('Invalid solid index size')
    try:index=json.loads(payload[8:8+index_size])
    except (ValueError,UnicodeError) as exc:raise RestoreError('Invalid solid index') from exc
    if not isinstance(index,list):raise RestoreError('Invalid solid index type')
    offset=8+index_size;entries={}
    for item in index:
        if not isinstance(item,list) or len(item)!=3:
            raise RestoreError('Invalid solid index entry')
        name,length,identity=item
        if not isinstance(name,str) or not (name=='metadata.rml' or re.fullmatch(r'[0-9a-f]{64}\.pkl',name)):
            raise RestoreError('Invalid solid member name')
        if name in entries or type(length) is not int or length<0 or length>len(payload)-offset:
            raise RestoreError('Duplicate, oversized or invalid solid member')
        if not isinstance(identity,str) or re.fullmatch(r'[0-9a-f]{64}',identity) is None:
            raise RestoreError('Invalid solid member identity')
        raw=payload[offset:offset+length];offset+=length
        if digest(raw)!=identity:raise RestoreError('Solid member hash differs')
        entries[name]=raw
    if offset!=len(payload):raise RestoreError('Trailing unindexed solid bytes')
    return entries


class SolidRepresentation:
    def __init__(self,graph,payloads=None):
        self.graph=graph;self.raw=dict(graph.archive if payloads is None else payloads)
        sizes=graph.sizes()
        for blob in graph.candidates:
            if blob not in self.raw or len(self.raw[blob])!=sizes[blob] or digest(self.raw[blob])!=blob:
                raise ValueError('Capture payload differs')
        self.cache={};self._last=None

    def files(self,selected,capabilities,k):
        selected=tuple(sorted(set(selected)))
        if not self.graph.roots<=set(selected)<=self.graph.candidates:
            raise ValueError('Invalid selected set or missing mandatory roots')
        header=metadata(self.graph,capabilities,k,'adaptive')
        key=(selected,digest(header))
        if self._last is not None and self._last[0]==key:return self._last[1]
        entries=[(blob+'.pkl',self.raw[blob]) for blob in selected]
        if selected not in self.cache:self.cache[selected]=container(entries)
        outside=self.cache[selected];inside=container([('metadata.rml',header)]+entries)
        files={'archive.rml':inside} if len(inside)<=len(outside)+len(header) else {'archive.rml':outside,'metadata.rml':header}
        self._last=(key,files)
        return files

    def write(self,selected,capabilities,k,destination):
        files=self.files(selected,capabilities,k);destination=Path(destination)
        destination.mkdir(parents=True,exist_ok=False)
        for name,raw in files.items():(destination/name).write_bytes(raw)
        actual=sum(p.stat().st_size for p in destination.iterdir() if p.is_file())
        if actual!=sum(map(len,files.values())):raise RestoreError('Solid physical byte accounting differs')
        loaded=SolidStore(destination)
        if loaded.retained!=set(selected) or any(loaded.load(blob)!=self.raw[blob] for blob in selected):
            raise RestoreError('Written solid store differs')
        return actual


class SolidStore(EncodedStore):
    def __init__(self,path):
        self.path=Path(path).resolve();archive=self.path/'archive.rml';external=self.path/'metadata.rml'
        if archive.is_symlink() or external.is_symlink():raise RestoreError('Solid files cannot be symlinks')
        if not archive.is_file() or archive.stat().st_size>MAX_SOLID_BYTES+len(MAGIC)+41:
            raise RestoreError('Missing or oversized solid archive')
        entries=unpack(archive.read_bytes());inside=entries.pop('metadata.rml',None)
        if (inside is None)==(not external.exists()):
            raise RestoreError('Solid metadata must occur exactly once')
        self.header=inside if inside is not None else external.read_bytes()
        self._load_metadata(parse_metadata(self.header))
        self.payloads={name[:-4]:raw for name,raw in entries.items()}
        self.retained=set(self.payloads)
        if not self.graph.roots<=self.retained<=self.sizes.keys():
            raise RestoreError('Missing mandatory roots or unknown solid artifacts')
        for blob,raw in self.payloads.items():
            if len(raw)!=self.sizes[blob] or digest(raw)!=blob:
                raise RestoreError('Solid canonical artifact differs')

    def load(self,blob):
        if blob not in self.retained:raise RestoreError('Solid artifact is not retained')
        return self.payloads[blob]

    def recover(self,output,*,target_ids=None,disabled=(),replay_execute=None,verify_environment=True):
        output=Path(output).resolve()
        if output.is_relative_to(self.path) or self.path.is_relative_to(output):
            raise ValueError('Choose output outside the persistent solid store')
        requested=None if target_ids is None else list(target_ids)
        targets=self.protected if requested is None else set(requested)
        arguments=dict(target_ids=requested,disabled=disabled,replay_execute=replay_execute,verify_environment=verify_environment)
        if targets<=self.protected and {self.graph.nodes[n].blob for n in targets}<=self.retained:
            result=super().recover(output,**arguments);scratch=0
        else:
            # The temporary files contain only this store's retained payloads.
            # They are removed after success or failure and never use a capture.
            with tempfile.TemporaryDirectory(prefix='recoverml-solid-replay-') as temporary:
                root=Path(temporary);(root/'blobs').mkdir();(root/'metadata.rml').write_bytes(self.header)
                for blob,raw in self.payloads.items():(root/'blobs'/(blob+'.pkl')).write_bytes(b'\0'+raw)
                scratch=len(self.header)+sum(len(raw)+1 for raw in self.payloads.values())
                result=EncodedStore(root).recover(output,**arguments)
        result['mode']='solid_export' if not result['operations'] else 'solid_replay'
        result['decoded_retained_bytes']=sum(map(len,self.payloads.values()))
        result['temporary_store_bytes']=scratch
        result['qualification']='Original canonical bytes; whole retained archive decoded in memory, with temporary retained files for replay. No latency or memory advantage is asserted.'
        return result


def main():
    import argparse,importlib
    from .core import Graph
    from .encoded_store import Representation
    from .delta_store import DeltaRepresentation,open_store
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('create');create.add_argument('--capture',type=Path,required=True)
    create.add_argument('--contract',type=Path,required=True);create.add_argument('--output',type=Path,required=True)
    restore=commands.add_parser('recover');restore.add_argument('--store',type=Path,required=True)
    restore.add_argument('--output',type=Path,required=True);restore.add_argument('--target',action='append')
    restore.add_argument('--disable',action='append',default=[])
    families={'base':'operators','capability':'capability_ops','census':'broad_workflows','scientific':'scientific_workflows','multiview':'multiview_workflow','retinal':'eyeai_workflow'}
    restore.add_argument('--operators',choices=sorted(families),default='base');args=parser.parse_args()
    if args.command=='create':
        from .component_retention import optimize
        graph=Graph.read(args.capture/'manifest.json')
        payloads={b:(args.capture/'blobs'/(b+'.pkl')).read_bytes() for b in graph.candidates}
        declared=json.loads(args.contract.read_bytes());caps=declared['capabilities'];k=declared['maximum_lost_groups']
        flat=Representation(graph,payloads);coupled=DeltaRepresentation(graph,payloads,flat.encoded);options=[]
        for name,representation in [('flat',flat),('delta',coupled)]:
            selected,status,diag=optimize(representation.cost_graph,caps,k)
            if status!='ok' or not diag.get('storage_optimal') or not diag.get('robust_certified'):
                raise RestoreError('No certified optimum for '+name)
            options.append((representation.size(selected,caps,k),name,representation,selected))
        solid=SolidRepresentation(graph,payloads);flat_selected=options[0][3]
        solid_files=solid.files(flat_selected,caps,k)
        options.append((sum(map(len,solid_files.values())),'solid-flat',solid,flat_selected))
        size,name,representation,selected=min(options,key=lambda option:(option[0],option[1]))
        actual=representation.write(selected,caps,k,args.output)
        if actual!=size:raise RestoreError('Portfolio store byte accounting differs')
        result=dict(status='PASS',format=name,store_bytes=size,
            candidate_bytes={option[1]:option[0] for option in options},
            qualification='Smallest of the flat optimum, the single-base delta optimum, and joint compression of the flat-optimum selection. This is not a globally optimal joint-compression selector.')
    else:
        def execute(op,values,parameters):return importlib.import_module('recoverml.'+families[args.operators]).execute(op,values,parameters)
        result=open_store(args.store).recover(args.output,target_ids=args.target,disabled=args.disable,replay_execute=execute)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
