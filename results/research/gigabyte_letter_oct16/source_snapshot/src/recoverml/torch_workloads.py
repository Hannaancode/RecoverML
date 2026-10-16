"""Real Digits CNN and 20 Newsgroups Transformer histories on a CPU."""
import hashlib
import re
import time
from collections import Counter
import numpy as np
from sklearn.datasets import load_digits, fetch_20newsgroups
from sklearn.model_selection import train_test_split
from .core import Graph, pack
from .operators import execute

CATEGORIES=['comp.graphics','rec.sport.baseball','sci.space','talk.politics.misc']


def dataset(config,seed):
    if config['dataset']=='digits':
        d=load_digits()
        x=np.ascontiguousarray(d.images[:,None]/16.,dtype=np.float32)
        y=np.ascontiguousarray(d.target,dtype=np.int64)
        split=train_test_split(np.arange(len(y)),test_size=.25,random_state=seed,stratify=y)
        return x,y,tuple(split),dict(name='Digits',classes=10,
            source='https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html',
            source_sha256=hashlib.sha256(pack((d.images,d.target))).hexdigest())
    if config['dataset']!='20newsgroups':
        raise ValueError('Unsupported PyTorch dataset')
    d=fetch_20newsgroups(subset='all',categories=CATEGORIES,
        remove=('headers','footers','quotes'),download_if_missing=False)
    # Balanced reproducible sample. Split precedes vocabulary fitting.
    rng=np.random.default_rng(seed)
    chosen=np.concatenate([rng.choice(np.flatnonzero(d.target==c),
        min(config['rows']//4,int((d.target==c).sum())),replace=False) for c in range(4)])
    texts=[d.data[i] for i in chosen]
    y=np.ascontiguousarray(d.target[chosen],dtype=np.int64)
    split=tuple(train_test_split(np.arange(len(y)),test_size=.25,random_state=seed,stratify=y))
    tokenize=lambda s: re.findall(r'[a-z]{2,}',s.lower())
    counts=Counter(word for i in split[0] for word in tokenize(texts[i]))
    terms=sorted(counts,key=lambda word:(-counts[word],word))[:config['vocabulary_size']-2]
    vocabulary={word:i+2 for i,word in enumerate(terms)}
    x=np.zeros((len(y),config['sequence_length']),dtype=np.int64)
    for i,text in enumerate(texts):
        tokens=[vocabulary.get(w,1) for w in tokenize(text)[:config['sequence_length']]]
        x[i,:len(tokens)]=tokens
    return x,y,split,dict(name='20 Newsgroups four-category subset',classes=4,
        categories=d.target_names,sample_source_indices=chosen.tolist(),
        source='https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_20newsgroups.html',
        source_sha256=hashlib.sha256(pack((texts,y))).hexdigest(),
        vocabulary=vocabulary,tokenization='lowercase ASCII words length >= 2; train-only vocabulary; pad=0 unknown=1')


def build_history(config,seed):
    x,y,split,provenance=dataset(config,seed)
    g=Graph();values={};tracking=[];started=time.perf_counter()
    def add(op,deps,params,value=None,replayable=True,mandatory=False,version=0):
        start=time.perf_counter()
        if value is None:
            value=execute(op,[values[d] for d in deps],params)
        elapsed=time.perf_counter()-start
        start=time.perf_counter()
        nid=g.add(op,deps,params,value,replayable,'torch',elapsed,version,mandatory)
        tracking.append(time.perf_counter()-start);values[nid]=value
        return nid
    source=add('input',[],{'kind':'prepared_features'},x,False,True)
    labels=add('input',[],{'kind':'labels'},y,False,True)
    membership=add('input',[],{'kind':'fixed_stratified_split'},split,False,True)
    stats=[]
    for version in range(config['versions']):
        features=source
        if config['boundary']=='nondeterministic':
            rng=np.random.default_rng()
            mask=rng.random(x.shape)<.03
            augmented=np.ascontiguousarray(np.where(mask,0,x))
            features=add('nondeterministic_augment',[source],{'version':version,
                'drop_fraction':.03},augmented,False,version=version)
        params=dict(architecture='cnn' if config['model']=='torch_cnn' else 'text_transformer',
            classes=provenance['classes'],seed=seed+version,
            learning_rate=config['learning_rate']*(1+version*.1),
            epochs=config['epochs'],batch_size=config.get('batch_size',64),
            vocabulary_size=config.get('vocabulary_size',2048),
            sequence_length=config.get('sequence_length',32))
        model=add('torch_train',[features,labels,membership],params,version=version)
        pred=add('torch_predict',[model,features,membership],{},version=version)
        g.targets[str(version)]=[model,pred]
        stats.append(dict(version=version,accuracy=float(np.mean(
            values[pred].argmax(1)==y[split[1]])),parameters=sum(
                a.size for a in values[model]['state'].values())))
    elapsed=time.perf_counter()-started
    return g,dict(capture_total_s=elapsed,lineage_serialization_s=sum(tracking),
        operator_total_s=sum(t['capture_s'] for t in g.capture_trace),
        metadata_and_serialization_s=elapsed-sum(t['capture_s'] for t in g.capture_trace),
        rows=len(y),version_accuracy=stats,dataset_provenance=provenance)
