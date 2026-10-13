"""Verified second scaler implementation for capability-loss experiments."""
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from .core import RestoreError,digest


def execute(op,values,params):
    if op=='scale_sklearn':
        expected=params.get('implementation_sha256')
        if expected!=digest(Path(__file__).read_bytes()):
            raise RestoreError('Scaler implementation contract mismatch')
        x,(mean,scale)=values
        fitted=StandardScaler()
        fitted.mean_=mean;fitted.scale_=scale;fitted.n_features_in_=x.shape[1]
        return np.ascontiguousarray(fitted.transform(x))
    from .operators import execute as original_execute
    return original_execute(op,values,params)
