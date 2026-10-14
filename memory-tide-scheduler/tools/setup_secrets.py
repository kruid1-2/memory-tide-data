"""Run in your terminal: never paste tokens into chat, shell arguments or files."""
import getpass
import os
from pathlib import Path
import secrets
import subprocess
import sys

os.chdir(Path(__file__).resolve().parents[1])
cli=['node','node_modules/wrangler/bin/wrangler.js','secret','put']
if not sys.stdin.isatty():raise SystemExit('Run in your own terminal; refusing a potentially echoed secret input.')
token=getpass.getpass('GitHub fine-grained PAT (hidden; only Actions write for memory-tide-data): ')
if not token.startswith('github_pat_'):raise SystemExit('Expected a fine-grained PAT. Nothing was uploaded.')
subprocess.run(cli+['GITHUB_DISPATCH_TOKEN'],input=token+'\n',text=True,check=True)
del token
path=Path('.probe-key')
if not path.exists():
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
subprocess.run(cli+['SCHEDULER_ADMIN_KEY'],input=path.read_text()+'\n',text=True,check=True)
print('Secrets uploaded. Probe key remains local with mode 600; no values were printed.')
