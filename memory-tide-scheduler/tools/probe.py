"""Invoke protected Cloudflare probe; never expose the local admin key."""
import argparse
import json
from pathlib import Path
import urllib.request
p=argparse.ArgumentParser();p.add_argument('worker_url');a=p.parse_args()
from urllib.parse import urlparse
u=urlparse(a.worker_url)
if u.scheme!='https' or not u.hostname or not u.hostname.endswith('.workers.dev'):p.error('Require the deployed HTTPS workers.dev URL')
key=(Path(__file__).resolve().parents[1]/'.probe-key').read_text().strip()
req=urllib.request.Request(a.worker_url.rstrip('/')+'/probe',method='POST',headers={'Authorization':'Bearer '+key})
with urllib.request.urlopen(req,timeout=60) as r:result=json.load(r)
print(json.dumps(result))
print('Dispatch acceptance is not evidence of collection. Audit the corresponding GitHub run and raw snapshot.')
