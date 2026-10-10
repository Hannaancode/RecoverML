"""Explicit supported operators. Scope and replay eligibility are independent."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def execute(op, values, p):
    if op == 'clean_block':
        return np.ascontiguousarray(np.sign(values[0]) * np.log1p(np.abs(values[0])))
    if op == 'concat':
        return np.ascontiguousarray(np.concatenate(values, axis=0))
    if op == 'affine_features':
        return np.ascontiguousarray(values[0] * p['scale'] + p['offset'])
    if op == 'split':
        train, test = train_test_split(np.arange(p['rows']), test_size=0.25,
                                       random_state=p['seed'])
        return (train, test)
    if op == 'fit_scaler':
        x, split = values
        scaler = StandardScaler().fit(x[split[0]])
        # Store numerical fitted state, avoiding opaque object serialization.
        return (scaler.mean_, scaler.scale_)
    if op == 'scale':
        x, (mean, scale) = values
        return np.ascontiguousarray((x - mean) / scale)
    if op == 'train':
        x, y, split = values
        if p['model'] == 'logistic':
            model = LogisticRegression(C=p['C'], solver='lbfgs', max_iter=400,
                                        tol=1e-9, random_state=p['seed'])
        else:
            model = RandomForestClassifier(n_estimators=p['trees'], max_depth=p['depth'],
                                           random_state=p['seed'], n_jobs=1)
        return model.fit(x[split[0]], y[split[0]])
    if op == 'predict':
        model, x, split = values
        return np.ascontiguousarray(model.predict_proba(x[split[1]]))
    # 'input' and 'external_features' have no replay implementation by design.
    raise ValueError(f'Unsupported replay operator: {op}')
