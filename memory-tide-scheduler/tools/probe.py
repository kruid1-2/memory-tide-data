"""Invoke protected probe using system curl CA trust; keys never enter argv."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse


def invoke_probe(worker_url,key,runner=subprocess.run):
    u=urlparse(worker_url)
    if u.scheme!='https' or not u.hostname or not u.hostname.endswith('.workers.dev') or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise ValueError('Require the deployed HTTPS workers.dev origin')
    if not re.fullmatch(r'[A-Za-z0-9_-]{30,200}',key):raise ValueError('Invalid local probe key')
    # No -k/--insecure, no secret in argv or a temporary file. curl uses OS trust.
    config='header = '+json.dumps('Authorization: Bearer '+key)+'\n'
    result=runner(['curl','--silent','--show-error','--fail-with-body','--max-time','120',
                   '--config','-','--request','POST',worker_url.rstrip('/')+'/probe'],
                  input=config.encode(),capture_output=True,check=False)
    if result.returncode:raise RuntimeError(f'Probe request failed (curl={result.returncode}); inspect Worker logs without exposing credentials')
    payload=json.loads(result.stdout)
    return {k:payload.get(k) for k in ('status','dispatch_id','run_id')}


def main():
    p=argparse.ArgumentParser();p.add_argument('worker_url');a=p.parse_args()
    key=(Path(__file__).resolve().parents[1]/'.probe-key').read_text().strip()
    print(json.dumps(invoke_probe(a.worker_url,key)))
    print('Dispatch acceptance is not evidence of collection. Audit the corresponding GitHub run and raw snapshot.')

if __name__=='__main__':main()
