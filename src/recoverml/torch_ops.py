"""Optional CPU PyTorch workloads with numerical state-dict artifact identity.

The checkpoint describes trained weights, not optimizer state or training resume.
No full-module pickle and no pretraining claim is used.
"""
from contextlib import contextmanager
import numpy as np


@contextmanager
def deterministic(seed):
    import torch
    previous = torch.are_deterministic_algorithms_enabled()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        try:
            yield
        finally:
            torch.use_deterministic_algorithms(previous)


def make_model(params):
    import torch
    from torch import nn
    if params['architecture'] == 'cnn':
        return nn.Sequential(nn.Conv2d(1,16,3,padding=1), nn.ReLU(),
            nn.MaxPool2d(2), nn.Conv2d(16,32,3,padding=1), nn.ReLU(),
            nn.Flatten(), nn.Linear(32*4*4,params['classes']))
    if params['architecture'] != 'text_transformer':
        raise ValueError('Unsupported PyTorch architecture')
    class TextTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding=nn.Embedding(params['vocabulary_size'],32,padding_idx=0)
            self.position=nn.Parameter(torch.zeros(1,params['sequence_length'],32))
            layer=nn.TransformerEncoderLayer(32,4,64,dropout=0.,batch_first=True)
            self.encoder=nn.TransformerEncoder(layer,2,enable_nested_tensor=False)
            self.head=nn.Linear(32,params['classes'])
        def forward(self,x):
            mask=x.eq(0)
            # Empty stripped posts and fully dropped augmentations must still
            # have one attention key. Otherwise inference attention yields NaN.
            mask=mask.clone()
            mask[mask.all(dim=1),0]=False
            hidden=self.encoder(self.embedding(x)+self.position,
                                src_key_padding_mask=mask)
            weight=(~mask).unsqueeze(-1)
            pooled=(hidden*weight).sum(1)/weight.sum(1).clamp(min=1)
            return self.head(pooled)
    return TextTransformer()


def train(values, params):
    import torch
    x,y,split=values
    with deterministic(params['seed']):
        model=make_model(params)
        optimizer=torch.optim.Adam(model.parameters(),lr=params['learning_rate'])
        tx=torch.from_numpy(np.array(x,copy=True))
        ty=torch.as_tensor(np.array(y,copy=True),dtype=torch.long)
        indices=np.asarray(split[0])
        model.train()
        for _ in range(params['epochs']):
            order=indices[torch.randperm(len(indices)).numpy()]
            for start in range(0,len(order),params['batch_size']):
                batch=order[start:start+params['batch_size']]
                optimizer.zero_grad(set_to_none=True)
                loss=torch.nn.functional.cross_entropy(model(tx[batch]),ty[batch])
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite training loss')
                loss.backward(); optimizer.step()
        state={k:np.array(v.detach().cpu().numpy(),copy=True)
               for k,v in sorted(model.state_dict().items())}
        if not all(np.isfinite(a).all() for a in state.values()):
            raise ValueError('Nonfinite checkpoint state')
        return {'recoverml_checkpoint':1,'architecture':params['architecture'],
                'params':dict(params),'state':state}


def predict(values):
    import torch
    checkpoint,x,split=values
    with deterministic(checkpoint['params']['seed']):
        model=make_model(checkpoint['params'])
        model.load_state_dict({k:torch.from_numpy(v.copy())
                               for k,v in checkpoint['state'].items()},strict=True)
        model.eval()
        results=[]
        with torch.no_grad():
            indices=np.asarray(split[1])
            for start in range(0,len(indices),64):
                batch=np.array(x[indices[start:start+64]],copy=True)
                results.append(model(torch.from_numpy(batch)).softmax(-1).numpy())
        output=np.ascontiguousarray(np.concatenate(results))
        if not np.isfinite(output).all():
            raise ValueError('Nonfinite inference output')
        return output


def execute(op,values,params):
    if op=='torch_train':
        return train(values,params)
    if op=='torch_predict':
        return predict(values)
    raise ValueError('Unknown torch operator')
