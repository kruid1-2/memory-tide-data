"""Dispatch provenance and shared-window admission; existing collector is unchanged.

The workflow's single fixed concurrency group serializes restore -> admission ->
collection -> persistence. Never run two independent writers against one branch.
"""
import datetime as dt
import fcntl
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory_tide.core import now,epoch
from memory_tide.live import collect_once,immutable,dumps,safe_run_id

WINDOW=900

def utc(seconds):return dt.datetime.fromtimestamp(seconds,dt.timezone.utc).isoformat().replace('+00:00','Z')

def run_collection(root,context,clock=now,outbox=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    rid=safe_run_id(str(context['run_id']));attempt=int(context['attempt'])
    if attempt<1:raise ValueError('Invalid attempt')
    current=epoch(clock());event=context['event'];source=context.get('trigger_source','manual')
    if event=='schedule':source='github-schedule'
    if source not in ('cloudflare-cron','cloudflare-probe','manual','github-schedule'):raise ValueError('Unknown trigger source')
    cloud=source.startswith('cloudflare-')
    if cloud and event!='workflow_dispatch':raise ValueError('Cloudflare must use workflow_dispatch')
    if cloud:
        planned=epoch(context['scheduled_at']);slot=int(planned//WINDOW)*WINDOW
        if planned!=slot:raise ValueError('Scheduled time must be on a 15-minute UTC boundary')
        if source=='cloudflare-cron' and context.get('dispatch_id')!=f'cf-{slot}':raise ValueError('Dispatch identity does not match slot')
        dispatched=epoch(context['dispatched_at'])
        if not slot<=dispatched<slot+WINDOW:raise ValueError('Dispatch time outside window')
    else:slot=int(current//WINDOW)*WINDOW
    rel=Path('scheduler/runs')/rid/f'{attempt}.json';path=root/rel
    def save(record):
        immutable(path,dumps(record))
        if outbox:
            dest=Path(outbox)/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
        return record
    with (root.parent/'.scheduler.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():return json.loads(path.read_text())
        record=dict(schema_version='1',run_id=rid,attempt=attempt,event=event,trigger_source=source,
                    dispatch_id=context.get('dispatch_id') if cloud else None,scheduled_at=utc(slot),
                    dispatched_at=context.get('dispatched_at') if cloud else None,
                    window_id=str(slot),workflow_created_at=context.get('workflow_created_at'),
                    workflow_started_at=context.get('workflow_started_at'),admitted_at=clock())
        # An old queued Cloudflare run must not create a late snapshot for a missed slot.
        # Previously committed same-run successes are recoverable even after expiry.
        own=root/'index'/f'{rid}.json'
        if own.exists():
            entry=json.loads(own.read_text())
        else:
            if cloud and not slot<=current<slot+WINDOW:
                return save(dict(record,status='expired_window',canonical_run_id=None))
            # Scan immutable commit indexes (including legacy ones), never just latest.
            matches=[]
            for p in (root/'index').glob('*.json'):
                candidate=json.loads(p.read_text())
                if slot<=epoch(candidate['timestamp'])<slot+WINDOW:matches.append(candidate)
            if matches:
                entry=min(matches,key=lambda x:epoch(x['timestamp']))
                return save(dict(record,status='duplicate_window',canonical_run_id=entry['snapshot_id'],snapshot_timestamp=entry['timestamp']))
            result=collect_once(root,rid,attempt,event=event,outbox=outbox)
            if result['status']=='failed':return save(dict(record,status='failed',canonical_run_id=None))
            entry=json.loads(own.read_text())
        timestamp=entry['timestamp'];actual=int(epoch(timestamp)//WINDOW)*WINDOW
        # Keep genuine late data but never count it as an on-time planned observation.
        quality=[] if actual==slot else ['received_after_window']
        claim=Path('scheduler/windows')/f'{actual}.json'
        immutable(root/claim,dumps(dict(window_id=str(actual),canonical_run_id=rid,snapshot_timestamp=timestamp)))
        if outbox:
            dest=Path(outbox)/claim;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((root/claim).read_bytes())
        return save(dict(record,status='success' if actual==slot else 'late_collection',canonical_run_id=rid,
                         snapshot_timestamp=timestamp,raw_sha256=entry['raw_sha256'],quality=quality,
                         local_files_finished_at=clock()))


def main():
    # No workflow inputs are interpolated into shell code; JSON comes from GitHub's event file.
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text());inputs=event.get('inputs') or {}
    context=dict(inputs,run_id=os.environ['GITHUB_RUN_ID'],attempt=int(os.environ['GITHUB_RUN_ATTEMPT']),event=os.environ['GITHUB_EVENT_NAME'])
    import urllib.request
    url=f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{context['run_id']}"
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'MEMORY-TIDE-Gate'})
    # Fail closed if actual workflow timing cannot be read; never invent a start time.
    with urllib.request.urlopen(req,timeout=15) as response:run=json.load(response)
    context.update(workflow_created_at=run['created_at'],workflow_started_at=run['run_started_at'])
    result=run_collection(Path(os.environ['DATA_DIR'])/'observations',context,outbox=os.environ.get('OUTBOX_DIR'))
    print(json.dumps(result,ensure_ascii=False))
    if result['status'] in ('failed','expired_window','late_collection'):raise SystemExit(1)

if __name__=='__main__':main()
