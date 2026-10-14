"""Verified second scaler implementation for capability-loss experiments."""
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from .core import RestoreError,digest


def restore_mlp(checkpoint):
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import LabelBinarizer
    if checkpoint.get('implementation_sha256')!=digest(Path(__file__).read_bytes()):
        raise RestoreError('Neural checkpoint implementation mismatch')
    model=MLPClassifier(**checkpoint['parameters'])
    model.__dict__.update(checkpoint['fitted_state'])
    labels=LabelBinarizer();labels.__dict__.update(checkpoint['label_state'])
    model._label_binarizer=labels
    return model


def execute(op,values,params):
    if op=='train_mlp':
        from .operators import execute as original_execute
        if params.get('implementation_sha256')!=digest(Path(__file__).read_bytes()):
            raise RestoreError('Neural training implementation mismatch')
        model=original_execute('train',values,params)
        state={key:getattr(model,key) for key in ('coefs_','intercepts_','classes_',
            'n_layers_','n_outputs_','out_activation_','n_features_in_')}
        result=dict(recoverml_checkpoint=1,kind='sklearn_mlp_inference_v1',
            implementation_sha256=digest(Path(__file__).read_bytes()),
            parameters=model.get_params(deep=False),fitted_state=state,
            label_state=dict(model._label_binarizer.__dict__))
        # This checkpoint preserves exact inference state, not optimizer state
        # for resuming training. Validate native-model inference at capture.
        from .core import pack,unpack
        restored=restore_mlp(unpack(pack(result)))
        if not np.array_equal(model.predict_proba(values[0]),restored.predict_proba(values[0])):
            raise RestoreError('Canonical neural inference differs')
        return result
    if op=='predict' and isinstance(values[0],dict) and values[0].get('kind')=='sklearn_mlp_inference_v1':
        model=restore_mlp(values[0]);x,split=values[1:]
        return np.ascontiguousarray(model.predict_proba(x[split[1]]))
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
