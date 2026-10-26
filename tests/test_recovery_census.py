import hashlib,json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from recoverml.core import Graph,pack,write_store,RestoreError
from recoverml.capability_retention import contract
from recoverml.file_recovery import recover_requested_files
from recoverml.broad_workflows import capture,execute,capabilities
from recoverml.component_retention import optimize
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from broad_recovery_worker import recover
from audit_recovery_census import trial_grid


class CensusRecoveryTests(unittest.TestCase):
    def test_missing_duplicate_and_relabelled_trials_cannot_pass(self):
        rows=[dict(case='fixed',method=m,repetition=r) for m in ('ours','native','direct') for r in range(3)]
        trial_grid(rows,['fixed'],['ours','native','direct'],3)
        for bad in (rows[:-1],rows+[rows[0]],[dict(r,case='replacement') for r in rows]):
            with self.assertRaises(ValueError):trial_grid(bad,['fixed'],['ours','native','direct'],3)

    def test_classification_regression_families_and_loss_modes_restore_exact_requested_files(self):
        with threadpool_limits(limits=1):
            for dataset in ('iris','linnerud'):
                for recipe in ('standard_linear','pca_neighbors','minmax_tree','robust_forest'):
                    graph,_=capture(dataset,recipe,1,20261026)
                    ids=graph.targets['0']
                    for loss in ('intact','preprocessing','broad'):
                        caps,k,disabled=capabilities(graph,loss)
                        selected,status,diag=optimize(graph,caps,k)
                        self.assertEqual(status,'ok');self.assertTrue(diag['storage_optimal'])
                        for engine in ('RecoverML','direct_control'):
                            with tempfile.TemporaryDirectory() as tmp:
                                store=Path(tmp)/'store';write_store(graph,selected,store)
                                (store/'capability_contract.json').write_bytes(contract(caps,k))
                                (store/'request.json').write_text(json.dumps(dict(targets=ids,disabled=disabled)))
                                result=recover(engine,store)
                                self.assertEqual(result['status'],'PASS')
                                for target in ids:
                                    blob=graph.nodes[target].blob
                                    self.assertEqual((store/'outputs'/(blob+'.pkl')).read_bytes(),graph.archive[blob])

    def test_sparse_store_enumeration_ignores_unknown_files_and_fails_on_corruption(self):
        from recoverml.witness import WitnessRestorer
        g=Graph(env={})
        root=g.add('input',[],{},np.arange(4.),False,'',0,0,mandatory=True)
        target=g.add('affine_features',[root],dict(scale=2.,offset=0.),np.arange(4.)*2,True,'',0,0)
        g.targets={'0':[target]}
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/'store';write_store(g,g.roots,store)
            (store/'blobs'/'unknown.pkl').write_bytes(b'ignored')
            self.assertEqual(pack(WitnessRestorer(g,store,verify_environment=False).get(target)),g.archive[g.nodes[target].blob])
            (store/'blobs'/(g.nodes[root].blob+'.pkl')).write_bytes(b'corrupt')
            with self.assertRaises(RestoreError):
                WitnessRestorer(g,store,verify_environment=False).get(target)
