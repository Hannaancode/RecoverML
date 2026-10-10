import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from recoverml.core import Graph, DiskRestorer, RestoreError, pack, write_store, validate_eviction
from recoverml.operators import execute
from recoverml.policies import select, exact
from recoverml.workloads import build_history


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.limits = threadpool_limits(limits=1)
        self.limits.__enter__()
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()
        self.limits.__exit__(None,None,None)

    def history(self, boundary='deterministic', model='logistic', change='parameters'):
        return build_history(dict(dataset='synthetic',rows=128,versions=2,model=model,
                                  change=change,boundary=boundary,block_rows=32),123)[0]

    def test_exact_replay_logistic_and_forest(self):
        for model in ('logistic','forest'):
            g = self.history(model=model)
            store = self.base/model
            write_store(g,g.roots,store)
            disk_graph = Graph.read(store/'manifest.json')
            self.assertEqual(disk_graph.archive,{})
            for version in g.targets:
                restored = DiskRestorer(disk_graph,store).version(version)
                for tid,value in zip(g.targets[version],restored):
                    self.assertEqual(pack(value),g.archive[g.nodes[tid].blob])

    def test_deep_affine_pipeline_replays_exactly(self):
        g,_ = build_history(dict(dataset='iris',rows=150,versions=2,
            model='logistic',change='parameters',boundary='deterministic',
            pre_boundary_depth=5),321)
        self.assertEqual(sum(n.op=='affine_features' for n in g.nodes.values()),5)
        store=self.base/'deep-affine'
        write_store(g,g.roots,store)
        replay_graph=Graph.read(store/'manifest.json')
        for version in g.targets:
            restored=DiskRestorer(replay_graph,store).version(version)
            for nid,value in zip(g.targets[version],restored):
                self.assertEqual(pack(value),g.archive[g.nodes[nid].blob])

    def test_loaded_model_inference_and_codec_roundtrip(self):
        from recoverml.core import unpack
        for model in ('logistic','forest'):
            g=self.history(model=model)
            train_node=g.nodes[g.targets['0'][0]]
            raw=g.archive[train_node.blob]
            loaded=unpack(raw)
            self.assertEqual(pack(loaded),raw)
            scaled=unpack(g.archive[g.nodes[train_node.deps[0]].blob])
            original=unpack(raw)
            np.testing.assert_array_equal(loaded.predict_proba(scaled),original.predict_proba(scaled))
            store=self.base/('loaded-'+model)
            # Load only the model; replay predictions to exercise the decoded tree.
            write_store(g,g.roots|{train_node.blob},store)
            DiskRestorer(Graph.read(store/'manifest.json'),store).version('0')

    def test_opaque_replay_fails_closed(self):
        g = self.history(boundary='opaque')
        store = self.base/'opaque'
        write_store(g,g.roots,store)
        self.assertFalse(g.coverage(g.roots)[0])
        with self.assertRaisesRegex(RestoreError,'non-replayable'):
            DiskRestorer(Graph.read(store/'manifest.json'),store).version('0')

    def test_corruption_detected_before_unpickle(self):
        g = self.history()
        store = self.base/'corrupt'
        write_store(g,g.candidates,store)
        target = g.nodes[g.targets['0'][0]]
        (store/'blobs'/(target.blob+'.pkl')).write_bytes(b'not a pickle')
        with self.assertRaisesRegex(RestoreError,'Corrupt'):
            DiskRestorer(Graph.read(store/'manifest.json'),store).version('0')

    def test_environment_mismatch_rejected(self):
        g = self.history()
        g.env['numpy'] = 'wrong'
        with self.assertRaisesRegex(RestoreError,'environment'):
            DiskRestorer(g,self.base)

    def test_wrong_replay_config_rejected_by_hash(self):
        g = self.history()
        store = self.base/'wrongconfig'
        write_store(g,g.roots,store)
        r = Graph.read(store/'manifest.json')
        r.nodes[r.targets['0'][0]].params['C'] = 300.0
        with self.assertRaisesRegex(RestoreError,'hash mismatch'):
            DiskRestorer(r,store).version('0')

    def test_global_fit_invalidates_and_local_blocks_share(self):
        g = self.history(change='data')
        scalers = [n for n in g.nodes.values() if n.op=='fit_scaler']
        self.assertEqual(len(scalers),2)
        self.assertNotEqual(scalers[0].blob,scalers[1].blob)
        clean = [n for n in g.nodes.values() if n.op=='clean_block']
        self.assertLess(len(clean),8)  # unchanged blocks share nodes across versions
        scaled = [n for n in g.nodes.values() if n.op=='scale']
        self.assertNotEqual(scaled[0].blob,scaled[1].blob)

    def test_unsafe_eviction_is_refused(self):
        g = self.history(boundary='opaque')
        protected = g.roots | {g.nodes[t].blob for ts in g.targets.values() for t in ts}
        with self.assertRaisesRegex(RestoreError,'recoverability'):
            validate_eviction(g,protected,protected-g.roots,g.size(g.candidates))
        with self.assertRaisesRegex(RestoreError,'input'):
            validate_eviction(g,protected,set(g.roots),g.size(g.candidates))

    def test_recoverability_retains_outputs_without_external_arrays(self):
        g = self.history(boundary='opaque')
        target_set = g.roots | {g.nodes[t].blob for ts in g.targets.values() for t in ts}
        selected = select(g,'recoverability',g.size(target_set))
        self.assertEqual(selected.status,'ok')
        self.assertTrue(g.coverage(selected.retained)[0])
        self.assertTrue(all(h['all_targets_recoverable'] for h in selected.history))
        store = self.base/'retained'
        write_store(g,selected.retained,store)
        for version in g.targets:
            DiskRestorer(Graph.read(store/'manifest.json'),store).version(version)

    def test_simple_target_baseline_is_safe(self):
        g = self.history(boundary='opaque')
        selection = select(g,'target_snapshots',g.size(g.candidates))
        self.assertTrue(g.coverage(selection.retained)[0])
        self.assertLess(g.size(selection.retained),g.size(g.candidates))

    def test_budget_failure_reported(self):
        g = self.history()
        self.assertEqual(select(g,'recoverability',1).status,'required_inputs_exceed_budget')

    def test_exact_oracle_threshold_and_heuristic(self):
        g = Graph()
        x = np.arange(80,dtype=float).reshape(40,2)
        root = g.add('input',[],{},x,False,'source',0.0,0,True)
        opaque = g.add('external_features',[root],{},x+0.123,False,'unknown',0.001,0)
        split_val = execute('split',[],{'rows':40,'seed':10})
        split = g.add('split',[],{'rows':40,'seed':10},split_val,True,'membership',0.001,0)
        fit_val = execute('fit_scaler',[x+0.123,split_val],{})
        fit = g.add('fit_scaler',[opaque,split],{},fit_val,True,'fitted-global',0.002,0)
        scaled_val = execute('scale',[x+0.123,fit_val],{})
        scaled = g.add('scale',[opaque,fit],{},scaled_val,True,'row-local',0.001,0)
        g.targets={'0':[fit], '1':[scaled]}
        oracle = exact(g)
        self.assertTrue(oracle['feasible'])
        self.assertFalse(exact(g,oracle['objective']-1)['feasible'])
        self.assertTrue(exact(g,oracle['objective'])['feasible'])
        selection = select(g,'recoverability',oracle['objective'])
        self.assertEqual(selection.status,'ok')
        self.assertTrue(g.coverage(selection.retained)[0])

    def test_journal_final_export_recovers_a_truncated_checkpoint(self):
        from recoverml.benchmark import AppendLog
        path=self.base/'journal.jsonl'
        with AppendLog(path,'w') as journal:
            journal.write('first\n')
            journal.checkpoint()
            path.write_text('')
            journal.write('second\n')
        self.assertEqual(path.read_text(),'first\nsecond\n')

    def test_cycles_rejected(self):
        g = self.history()
        nid = g.targets['0'][0]
        g.nodes[nid].deps = [nid]
        with self.assertRaisesRegex(ValueError,'Cyclic'):
            g.coverage(g.roots)

    def test_branched_pipeline_restores_all_models_and_predictions(self):
        g,_ = build_history(dict(dataset='synthetic',rows=128,versions=2,
            model='logistic',change='parameters',boundary='opaque',branches=3),123)
        self.assertEqual(len(g.targets['0']),6)
        self.assertEqual(sum(n.op=='scale' for n in g.nodes.values()),2)
        selected = select(g,'recoverability_v2',g.size(g.candidates))
        store = self.base/'branched'
        write_store(g,selected.retained,store)
        for version in g.targets:
            restored = DiskRestorer(Graph.read(store/'manifest.json'),store).version(version)
            for nid,value in zip(g.targets[version],restored):
                self.assertEqual(pack(value),g.archive[g.nodes[nid].blob])


if __name__=='__main__':
    unittest.main()
