"""Shell orchestration checks; fake Python never supplies benchmark measurements."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunnerTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        script = Path(__file__).resolve().parents[1]/'run_benchmarks.sh'
        shutil.copyfile(script,self.root/'run_benchmarks.sh')
        commands = self.root/'bin'
        commands.mkdir()
        python = commands/'python'
        python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$CALL_LOG"\nexit "${FAKE_EXIT:-0}"\n')
        python.chmod(0o755)
        self.calls = self.root/'calls.txt'
        self.env = dict(os.environ,PATH=str(commands)+os.pathsep+os.environ['PATH'],
                        CALL_LOG=str(self.calls))
        self.out = self.root/'nested'/'results'

    def invoke(self, **overrides):
        return subprocess.run(['bash',str(self.root/'run_benchmarks.sh'),str(self.out)],
                              capture_output=True,text=True,env=dict(self.env,**overrides))

    def test_existing_results_are_unchanged(self):
        self.out.mkdir(parents=True)
        log = self.out/'tests.txt'
        log.write_bytes(b'original validation evidence\n')
        result = self.invoke()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Use a new output folder',result.stderr)
        self.assertEqual(log.read_bytes(),b'original validation evidence\n')
        self.assertFalse(self.calls.exists())

    def test_failure_stops_remaining_commands(self):
        result = self.invoke(FAKE_EXIT='7')
        self.assertEqual(result.returncode,7)
        self.assertEqual(len(self.calls.read_text().splitlines()),1)
        self.assertNotIn('Complete results',result.stdout)

    def test_new_folder_runs_all_stages_in_order(self):
        result = self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(len(calls),4)
        self.assertTrue(calls[0].startswith('-m unittest discover'))
        self.assertTrue(calls[1].startswith('-m recoverml benchmark'))
        self.assertTrue(calls[2].startswith('-m recoverml.audit'))
        self.assertTrue(calls[3].startswith('-m recoverml.performance'))
        self.assertTrue((self.out/'tests.txt').exists())
        self.assertIn('Complete results',result.stdout)
