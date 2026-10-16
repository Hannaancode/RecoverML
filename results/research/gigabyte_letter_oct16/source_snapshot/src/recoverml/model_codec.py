"""Canonical numerical/model state codec for explicitly supported sklearn classes.

Defines artifact identity independently of pickle reference-sharing and unused C
struct padding. It is not a canonical codec for arbitrary Python objects.
"""
import base64
import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.tree._tree import Tree

PREFIX = b'RECOVERML-MODEL-V1\n'
CLASSES = {c.__name__:c for c in (RandomForestClassifier, LogisticRegression, DecisionTreeClassifier)}


def encode(obj):
    if isinstance(obj,np.ndarray):
        arr = np.ascontiguousarray(obj)
        if arr.dtype.names:
            clean = np.zeros(arr.shape,dtype=arr.dtype)
            clean.view(np.uint8).fill(0)
            for name in arr.dtype.names:
                clean[name] = arr[name]
            arr=clean
            dtype={'structured':{'names':list(arr.dtype.names),
                    'formats':[arr.dtype.fields[n][0].str for n in arr.dtype.names],
                    'offsets':[arr.dtype.fields[n][1] for n in arr.dtype.names],
                    'itemsize':arr.dtype.itemsize}}
        else:
            dtype={'str':arr.dtype.str}
        return {'tag':'array','shape':arr.shape,'dtype':dtype,
                'data':base64.b64encode(arr.tobytes()).decode('ascii')}
    if isinstance(obj,np.generic):
        return {'tag':'scalar','dtype':obj.dtype.str,'value':encode(obj.item())}
    if isinstance(obj,Tree):
        return {'tag':'tree','features':obj.n_features,'outputs':obj.n_outputs,
                'classes':encode(obj.n_classes),'state':encode(obj.__getstate__())}
    if type(obj).__name__ in CLASSES and isinstance(obj,tuple(CLASSES.values())):
        return {'tag':'estimator','class':type(obj).__name__,'state':encode(obj.__dict__)}
    if isinstance(obj,dict):
        if not all(isinstance(k,str) for k in obj):
            raise TypeError('Model state requires string dictionary keys')
        return {'tag':'dict','value':{k:encode(v) for k,v in sorted(obj.items())}}
    if isinstance(obj,tuple):
        return {'tag':'tuple','value':[encode(v) for v in obj]}
    if isinstance(obj,list):
        return {'tag':'list','value':[encode(v) for v in obj]}
    if obj is None or isinstance(obj,(str,int,float,bool)):
        return obj
    raise TypeError(f'Unsupported canonical model state: {type(obj)}')


def decode(obj):
    if not isinstance(obj,dict):
        return obj
    tag=obj['tag']
    if tag=='array':
        d=obj['dtype']
        dtype=np.dtype(d['structured']) if 'structured' in d else np.dtype(d['str'])
        return np.frombuffer(base64.b64decode(obj['data']),dtype=dtype).copy().reshape(obj['shape'])
    if tag=='scalar':
        return np.asarray(decode(obj['value']),dtype=obj['dtype'])[()]
    if tag=='tree':
        t=Tree(obj['features'],decode(obj['classes']),obj['outputs'])
        t.__setstate__(decode(obj['state']))
        return t
    if tag=='estimator':
        c=CLASSES[obj['class']]()
        c.__dict__.update(decode(obj['state']))
        return c
    if tag=='dict':
        return {k:decode(v) for k,v in obj['value'].items()}
    if tag=='tuple':
        return tuple(decode(v) for v in obj['value'])
    if tag=='list':
        return [decode(v) for v in obj['value']]
    raise ValueError('Unsupported canonical model tag')


def dumps(model):
    return PREFIX+json.dumps(encode(model),sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def loads(raw):
    if not raw.startswith(PREFIX):
        raise ValueError('Unsupported model codec version')
    return decode(json.loads(raw[len(PREFIX):]))
