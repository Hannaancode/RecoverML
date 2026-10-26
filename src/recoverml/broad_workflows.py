"""Fresh public-data recipe families for the fixed recovery census."""
from pathlib import Path
import time
import numpy as np
from sklearn import datasets
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from threadpoolctl import threadpool_limits
from .core import Graph, RestoreError, digest, pack, unpack

DATASETS=('iris','wine','breast_cancer','digits','diabetes','linnerud')
RECIPES=('standard_linear','pca_neighbors','minmax_tree','robust_forest')


def signature():
    return digest(Path(__file__).read_bytes())


def estimator(recipe, classification, parameters):
    classes={'standard_linear':(LogisticRegression,Ridge),
             'pca_neighbors':(KNeighborsClassifier,KNeighborsRegressor),
             'minmax_tree':(DecisionTreeClassifier,DecisionTreeRegressor),
             'robust_forest':(RandomForestClassifier,RandomForestRegressor)}
    return classes[recipe][0 if classification else 1](**parameters)


def snapshot(model, recipe, classification, parameters):
    state=dict(model.__dict__)
    trees=None
    if recipe=='robust_forest':
        trees=[dict(parameters=t.get_params(),state=dict(t.__dict__)) for t in state.pop('estimators_')]
        # Base estimator templates are not fitted outputs and can be recreated.
        state.pop('estimator',None);state.pop('estimator_',None);state.pop('base_estimator_',None)
    fortran=[k for k,v in state.items() if isinstance(v,np.ndarray) and v.flags.f_contiguous and not v.flags.c_contiguous]
    return dict(recoverml_checkpoint=1,kind='recovery_census_v1',implementation=signature(),
        recipe=recipe,classification=classification,parameters=parameters,state=state,trees=trees,fortran=fortran)


def restore(checkpoint):
    if checkpoint['implementation']!=signature():
        raise RestoreError('Census checkpoint implementation differs')
    model=estimator(checkpoint['recipe'],checkpoint['classification'],checkpoint['parameters'])
    model.__dict__.update(checkpoint['state'])
    for key in checkpoint['fortran']:
        model.__dict__[key]=np.asfortranarray(model.__dict__[key])
    if checkpoint['trees'] is not None:
        tree_class=DecisionTreeClassifier if checkpoint['classification'] else DecisionTreeRegressor
        model.estimators_=[]
        for row in checkpoint['trees']:
            tree=tree_class(**row['parameters']);tree.__dict__.update(row['state']);model.estimators_.append(tree)
        model.estimator_=tree_class()
    return model


def execute(op, values, p):
    if p['implementation']!=signature():
        raise RestoreError('Census operator implementation differs')
    with threadpool_limits(limits=1):
        if op=='census_preprocess':
            x,split=values;train=split[0]
            recipe=p['recipe']
            scaler={'standard_linear':StandardScaler,'pca_neighbors':StandardScaler,
                    'minmax_tree':MinMaxScaler,'robust_forest':RobustScaler}[recipe]().fit(x[train])
            x=scaler.transform(x)
            if recipe=='pca_neighbors':
                pca=PCA(n_components=min(8,x.shape[1],len(train)),svd_solver='full').fit(x[train])
                x=pca.transform(x)
            return np.ascontiguousarray(x)
        if op=='census_train':
            x,y,split=values
            model=estimator(p['recipe'],p['classification'],p['parameters'])
            model.fit(x[split[0]],y[split[0]])
            result=snapshot(model,p['recipe'],p['classification'],p['parameters'])
            reconstructed=restore(unpack(pack(result)))
            if not np.array_equal(model.predict(x[split[1]]),reconstructed.predict(x[split[1]])):
                raise RestoreError('Native census checkpoint differs')
            return result
        if op=='census_predict':
            model,x,split=values
            return np.ascontiguousarray(restore(model).predict(x[split[1]]))
    raise RestoreError('Unsupported census operator')


def capture(dataset, recipe, versions, seed):
    if dataset not in DATASETS or recipe not in RECIPES or versions not in (1,4,16):
        raise ValueError('Outside fixed census catalogue')
    data=getattr(datasets,'load_'+dataset)()
    classification=dataset not in ('diabetes','linnerud')
    x=np.ascontiguousarray(data.data,dtype=np.float64)
    target=data.target[:,0] if dataset=='linnerud' else data.target
    y=np.ascontiguousarray(target,dtype=np.int64 if classification else np.float64)
    train,test=train_test_split(np.arange(len(y),dtype=np.int64),test_size=.25,random_state=seed,
                               stratify=y if classification else None)
    split=(np.ascontiguousarray(train),np.ascontiguousarray(test))
    g=Graph();values={}
    def add(op,deps,p,value=None,mandatory=False,version=0):
        p=dict(p,implementation=signature());clock=time.perf_counter()
        if value is None:value=execute(op,[values[d] for d in deps],p)
        node=g.add(op,deps,p,value,not mandatory,op,time.perf_counter()-clock,version,mandatory=mandatory)
        values[node]=value
        return node
    rx=add('input',[],{'dataset':dataset,'kind':'features'},x,True)
    ry=add('input',[],{'dataset':dataset,'kind':'labels'},y,True)
    rs=add('input',[],{'kind':'membership','seed':seed},split,True)
    feature=add('census_preprocess',[rx,rs],{'recipe':recipe})
    for version in range(versions):
        if recipe=='standard_linear':
            params=(dict(C=10.**(-2+version/5),solver='lbfgs',max_iter=2000,tol=1e-8,random_state=seed+version)
                    if classification else dict(alpha=10.**(-2+version/5),solver='svd'))
        elif recipe=='pca_neighbors':
            params=dict(n_neighbors=min(1+version,len(train)),weights=('uniform','distance')[version%2],
                        algorithm='brute',n_jobs=1)
        elif recipe=='minmax_tree':
            params=dict(max_depth=2+version%6,random_state=seed+version)
        else:
            params=dict(n_estimators=8+2*(version%4),max_depth=6,random_state=seed+version,n_jobs=1)
        p=dict(recipe=recipe,classification=classification,parameters=params)
        model=add('census_train',[feature,ry,rs],p,version=version)
        prediction=add('census_predict',[model,feature,rs],{},version=version)
        g.targets[str(version)]=[model,prediction]
    return g,dict(dataset=dataset,recipe=recipe,versions=versions,seed=seed,
                  rows=len(y),columns=x.shape[1],classification=classification)


def capabilities(graph, loss):
    if loss=='intact':return {},0,[]
    if loss=='preprocessing':
        caps={n.id:'preprocessing' for n in graph.nodes.values() if n.op=='census_preprocess'}
        return caps,1,['preprocessing']
    if loss=='broad':
        caps={n.id:n.op for n in graph.nodes.values() if n.op in ('census_train','census_predict')}
        return caps,2,['census_train','census_predict']
    raise ValueError('Unknown census loss')
