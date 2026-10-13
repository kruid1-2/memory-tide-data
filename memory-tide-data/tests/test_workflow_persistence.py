"""Local bare Git repository exercises persistence without GitHub credentials."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from memory_tide.live import collect_once
from test_live_collection import response

DEPLOYMENT=Path(__file__).resolve().parents[1]/'deployment'


class WorkflowPersistenceTests(unittest.TestCase):
    def test_fresh_runner_restores_history_and_idempotent_run_does_not_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);origin=root/'server/test/repo.git';origin.parent.mkdir(parents=True)
            subprocess.run(['git','init','--bare',str(origin)],check=True,capture_output=True)
            env=dict(os.environ,GITHUB_TOKEN='unused-local-test-value',GITHUB_SERVER_URL=(root/'server').as_uri(),
                     GITHUB_REPOSITORY='test/repo',RUNNER_TEMP=str(root),GITHUB_RUN_ATTEMPT='1')
            commits=[];first_raw=None
            for n in (1,2):
                store=root/f'runner{n}';env.update(DATA_DIR=str(store),GITHUB_RUN_ID=f'run{n}')
                subprocess.run(['bash',str(DEPLOYMENT/'restore_data.sh')],env=env,check=True,capture_output=True)
                result=collect_once(store/'observations',f'run{n}',1,lambda:(response(n*100),{}),
                                    timestamp=f'2026-10-13T10:{(n-1)*15:02}:00+08:00')
                self.assertEqual(result['status'],'success')
                if n==1:first_raw=(store/'observations'/result['raw_path']).read_bytes()
                else:
                    raw1=list((store/'observations/raw').glob('**/*run1.json'))[0]
                    self.assertEqual(raw1.read_bytes(),first_raw)
                subprocess.run(['bash',str(DEPLOYMENT/'persist_data.sh')],env=env,check=True,capture_output=True)
                commits.append(subprocess.check_output(['git','--git-dir',str(origin),'rev-parse','refs/heads/data']).decode().strip())
            self.assertNotEqual(commits[0],commits[1])
            self.assertEqual(len(list((store/'observations/snapshots').glob('**/*.json'))),2)
            collect_once(store/'observations','run2',2,lambda:self.fail('no duplicate fetch'))
            subprocess.run(['bash',str(DEPLOYMENT/'persist_data.sh')],env=env,check=True,capture_output=True)
            after=subprocess.check_output(['git','--git-dir',str(origin),'rev-parse','refs/heads/data']).decode().strip()
            self.assertEqual(after,commits[1])

    def test_failure_attempt_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);origin=root/'server/test/repo.git';origin.parent.mkdir(parents=True)
            subprocess.run(['git','init','--bare',str(origin)],check=True,capture_output=True)
            store=root/'runner';env=dict(os.environ,DATA_DIR=str(store),GITHUB_TOKEN='unused-local-test-value',
                     GITHUB_SERVER_URL=(root/'server').as_uri(),GITHUB_REPOSITORY='test/repo',RUNNER_TEMP=str(root),
                     GITHUB_RUN_ID='bad',GITHUB_RUN_ATTEMPT='1')
            subprocess.run(['bash',str(DEPLOYMENT/'restore_data.sh')],env=env,check=True,capture_output=True)
            collect_once(store/'observations','bad',1,lambda:(b'<html>Visitor</html>',{}))
            subprocess.run(['bash',str(DEPLOYMENT/'persist_data.sh')],env=env,check=True,capture_output=True)
            payload=subprocess.check_output(['git','--git-dir',str(origin),'show','data:observations/status.json'])
            state=json.loads(payload);self.assertEqual(state['last_attempt_status'],'failed');self.assertIsNone(state['last_success_at'])


if __name__=='__main__':unittest.main()
