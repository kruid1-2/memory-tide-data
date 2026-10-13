import json
import os
from pathlib import Path

path=Path(os.environ['DATA_DIR'])/'observations/status.json'
state=json.loads(path.read_text()) if path.exists() else {}
repo=os.environ['GITHUB_REPOSITORY'];base=os.environ['GITHUB_SERVER_URL']+'/'+repo
lines=['# MEMORY TIDE collection',
       f"- Collection: {state.get('last_attempt_status', 'no status written')}",
       f"- Last attempt: {state.get('last_attempt_at')}",
       f"- Last success (Beijing): {state.get('last_success_at')}",
       f"- Persistence step: {os.environ.get('PERSIST_OUTCOME', 'unknown')}",
       f'- [Persistent status]({base}/blob/data/observations/status.json)',
       f'- [Latest success]({base}/blob/data/observations/latest.json)',
       f'- [Latest trends]({base}/blob/data/observations/latest_trends.json)']
if state.get('last_error'):lines.append('- Error: '+state['last_error']['type'])
with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('\n'.join(lines)+'\n')
