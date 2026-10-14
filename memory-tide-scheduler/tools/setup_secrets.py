"""Run in your terminal: never paste tokens into chat, shell arguments or files."""
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

os.chdir(Path(__file__).resolve().parents[1])
os.environ.setdefault('WRANGLER_LOG_PATH',str(Path.cwd()/'.wrangler/logs'))
os.environ.setdefault('WRANGLER_SEND_METRICS','false')
cli=['node','node_modules/wrangler/bin/wrangler.js','secret','put']
if not sys.stdin.isatty():raise SystemExit('Run in your own terminal; refusing a potentially echoed secret input.')
token=getpass.getpass('GitHub fine-grained PAT (hidden; only Actions write for memory-tide-data): ')
if not re.fullmatch(r'github_pat_[A-Za-z0-9_]{40,250}',token):
    raise SystemExit('This does not look like a complete fine-grained PAT. Nothing was uploaded. Copy the full generated value using its copy button.')
# Check identity before changing the Cloudflare Secret. Discard the response body;
# pass credentials via stdin rather than argv, and print only the HTTP code.
config='header = '+json.dumps('Authorization: Bearer '+token)+'\n'
check=subprocess.run(['curl','--silent','--show-error','--max-time','20','--config','-',
                      '--header','Accept: application/vnd.github+json','--header','User-Agent: MEMORY-TIDE-Setup',
                      '--output',os.devnull,'--write-out','%{http_code}','https://api.github.com/user'],
                     input=config.encode(),capture_output=True,check=False)
if check.returncode or check.stdout.strip()!=b'200':
    code=check.stdout.decode(errors='replace').strip()
    if not re.fullmatch(r'\d{3}',code):code='unavailable'
    raise SystemExit('GitHub credential check did not pass (HTTP '+code+'). Nothing was uploaded. Re-copy or regenerate the token; do not share its value.')
print('GitHub credential accepted. Uploading directly to Cloudflare Secret...')
subprocess.run(cli+['GITHUB_DISPATCH_TOKEN'],input=token+'\n',text=True,check=True)
del token,config
path=Path('.probe-key')
if not path.exists():
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
subprocess.run(cli+['SCHEDULER_ADMIN_KEY'],input=path.read_text()+'\n',text=True,check=True)
print('Secrets uploaded. Probe key remains local with mode 600; no values were printed.')
