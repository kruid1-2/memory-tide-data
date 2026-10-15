"""Temporary reconnecting Wrangler capture. Raw sessions stay separate and private."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid


def utc():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def exclusive(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'capture.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def capture(root, command, max_sessions=None, retry_seconds=5):
    root=Path(root)
    with exclusive(root):
        count=0;child=None
        def stop(signum,frame):
            if child and child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
            raise SystemExit(0)
        old={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
        try:
            while max_sessions is None or count<max_sessions:
                name='tail-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
                started=utc()
                with (root/(name+'.jsonl')).open('xb') as out, (root/(name+'.stderr')).open('xb') as err:
                    child=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True,
                        env=dict(os.environ,WRANGLER_SEND_METRICS='false',WRANGLER_LOG_PATH='.wrangler/logs'))
                    state=dict(supervisor_pid=os.getpid(),child_pid=child.pid,started_at=started,raw_file=name+'.jsonl')
                    (root/'current.json').write_text(json.dumps(state,indent=2)+'\n')
                    print(json.dumps(dict(status='subscribing',started_at=started,raw_file=name+'.jsonl')),flush=True)
                    code=child.wait()
                with (root/'connections.jsonl').open('a') as f:
                    f.write(json.dumps(dict(state,ended_at=utc(),exit_code=code))+'\n')
                child=None;count+=1
                if max_sessions is None or count<max_sessions:time.sleep(retry_seconds)
        finally:
            if child and child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            for s,handler in old.items():signal.signal(s,handler)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='reports/acceptance-capture');a=p.parse_args()
    capture(a.out,['npx','wrangler','tail','memory-tide-scheduler','--format','json'])
