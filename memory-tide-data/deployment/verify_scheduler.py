"""Audit consecutive Cloudflare windows, actual GitHub runs and committed raw bytes."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.verify_cloud import api,data_file,verify_run
from memory_tide.core import epoch,now
from deployment.scheduled_collect import utc


def summarize(start,count,records,checked):
    windows=[];times=[]
    for slot in range(int(start),int(start)+900*count,900):
        candidates=[r for r in records if r['slot']==slot and r.get('trigger_source')=='cloudflare-cron']
        good=[r for r in candidates if r.get('verified') and slot<=r.get('snapshot_epoch',-1)<slot+900]
        row=min(good,key=lambda r:r['snapshot_epoch']) if good else None
        status='success' if row else 'pending' if checked<slot+900 else 'missing_or_unverified'
        windows.append(dict(scheduled_at=utc(slot),status=status,evidence=row,candidates=candidates))
        if row:times.append(row['snapshot_epoch'])
    successful=sum(w['status']=='success' for w in windows)
    return dict(schema_version='1',checked_at=utc(checked),expected_interval_seconds=900,target_windows=count,
                successful_windows=successful,missing_windows=sum(w['status']=='missing_or_unverified' for w in windows),
                pending_windows=sum(w['status']=='pending' for w in windows),
                observation_start_at=utc(start),observation_end_at=utc(start+900*count),
                complete=successful==count and checked>=start+900*count,
                sampling_intervals_seconds=[b-a for a,b in zip(times,times[1:])],windows=windows)


def worker_logs(path):
    """Read JSONL or the streamed JSON objects printed by wrangler tail --format json."""
    text=Path(path).read_text();decoder=json.JSONDecoder();items=[];offset=0
    while offset<len(text):
        if text[offset].isspace():offset+=1;continue
        value,used=decoder.raw_decode(text,offset);offset=used
        if isinstance(value,dict) and value.get('component')=='memory-tide-scheduler':items.append(value)
        for log in value.get('logs',[]) if isinstance(value,dict) else []:
            for message in log.get('message',[]):
                if isinstance(message,str):
                    try:item=json.loads(message)
                    except json.JSONDecodeError:continue
                    if isinstance(item,dict) and item.get('component')=='memory-tide-scheduler':items.append(item)
    return items


def audit(repo,start,count,logs):
    # Public repo contents are evidence; the token never appears in audit output.
    # Filter authoritative GitHub creation times before fetching metadata. Scanning
    # every past run made each heartbeat grow indefinitely and fail on unrelated
    # requests. A valid dispatch cannot be created outside this observation range.
    eligible=set();page=1
    while True:
        query=urlencode(dict(event='workflow_dispatch',created=f'{utc(start)}..{utc(start+count*900)}',per_page=100,page=page))
        batch=api(f'repos/{repo}/actions/workflows/collect-weibo.yml/runs?{query}')['workflow_runs']
        eligible.update(str(run['id']) for run in batch)
        if len(batch)<100:break
        page+=1
    tree=api(f'repos/{repo}/git/trees/data?recursive=1')
    if tree.get('truncated'):raise ValueError('Data tree truncated; cannot certify complete audit')
    records=[]
    for item in tree['tree']:
        name=item['path']
        if not name.startswith('observations/scheduler/runs/') or not name.endswith('.json'):continue
        if name.split('/')[3] not in eligible:continue
        metadata=json.loads(data_file(repo,name.removeprefix('observations/')))
        if metadata.get('trigger_source')!='cloudflare-cron':continue
        slot=epoch(metadata['scheduled_at'])
        if not start<=slot<start+count*900:continue
        record=dict(metadata,slot=int(slot),verified=False)
        records.append(record)
        try:
            rid=int(metadata['run_id']);run=api(f'repos/{repo}/actions/runs/{rid}')
            if run['event']!='workflow_dispatch' or run['head_branch']!='main':raise ValueError('Wrong event/branch')
            if run['status']!='completed' or run['conclusion']!='success':raise ValueError('Dispatch run not successful')
            jobs=api(f'repos/{repo}/actions/runs/{rid}/jobs')['jobs']
            steps={s['name']:s for job in jobs if job['name']=='collect' for s in job['steps']}
            required=['Collect genuine current data','Verify saved response and last successful snapshot','Persist snapshots or failure log to GitHub']
            if any(steps.get(n,{}).get('conclusion')!='success' for n in required):raise ValueError('Dispatch step failed')
            accepted=[l for l in logs if l.get('status')=='dispatch_accepted' and l.get('trigger_source')=='cloudflare-cron'
                      and l.get('dispatch_id')==metadata['dispatch_id'] and epoch(l['scheduled_at'])==slot
                      and epoch(l['dispatched_at'])==epoch(metadata['dispatched_at'])
                      and (l.get('run_id') is None or l['run_id']==rid)]
            if not accepted:raise ValueError('Missing genuine Cloudflare cron log; metadata alone is insufficient')
            if metadata['status'] not in ('success','duplicate_window'):raise ValueError('No successful window collection')
            canonical=int(metadata['canonical_run_id']);canonical_run=api(f'repos/{repo}/actions/runs/{canonical}')
            observation=verify_run(repo,canonical_run)
            sample=epoch(observation['snapshot_timestamp'])
            if not slot<=sample<slot+900:raise ValueError('Sample outside its claimed time window')
            cjobs=api(f'repos/{repo}/actions/runs/{canonical}/jobs')['jobs']
            persisted=[s['completed_at'] for job in cjobs for s in job['steps'] if s['name']=='Persist snapshots or failure log to GitHub' and s['conclusion']=='success']
            if not persisted:raise ValueError('No successful persistence completion time')
            record.update(verified=True,snapshot_epoch=sample,snapshot=observation,
                          workflow_created_at=run['created_at'],workflow_started_at=run['run_started_at'],
                          persistence_confirmed_at=persisted[-1],cloudflare_log_verified=True,
                          trigger_delay_seconds=epoch(metadata['dispatched_at'])-slot,
                          github_start_delay_seconds=epoch(run['run_started_at'])-slot,
                          job_started_at=min(job['started_at'] for job in jobs if job.get('started_at')),
                          runner_queue_seconds=min(epoch(job['started_at']) for job in jobs if job.get('started_at'))-epoch(run['created_at']),
                          sample_delay_seconds=sample-slot,persistence_delay_seconds=epoch(persisted[-1])-slot)
        except Exception as exc:
            # subprocess error text can include commands; only expose controlled type/message.
            record['verification_error']=str(exc)[:200] if isinstance(exc,ValueError) else type(exc).__name__
    report=summarize(start,count,records,epoch(now()));report['repository']=repo
    report['semantics']='Success needs real Cloudflare cron log, successful GitHub steps, committed raw reparse, sample inside its window. Dispatch accepted alone is insufficient.'
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='kruid1-2/memory-tide-data');p.add_argument('--start',required=True,help='First UTC cron window, e.g. 2026-10-14T08:00:00Z');p.add_argument('--count',type=int,default=8);p.add_argument('--logs',required=True);p.add_argument('--out',default='live/cloudflare_windows.json');a=p.parse_args()
    start=epoch(a.start)
    if start%900 or not 1<=a.count<=96:p.error('Require a UTC quarter-hour and count 1..96')
    result=audit(a.repo,start,a.count,worker_logs(a.logs));out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
