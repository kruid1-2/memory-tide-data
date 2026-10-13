"""Verify actual GitHub schedule events against permanently committed raw snapshots."""
import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory_tide.live import parse_payload
from memory_tide.core import now


def api(path):
    return json.loads(subprocess.check_output(['gh','api',path],stderr=subprocess.PIPE))


def data_file(repo,path):
    response=api(f'repos/{repo}/contents/observations/{path}?ref=data')
    if response.get('encoding')!='base64':raise ValueError('Unexpected GitHub content encoding')
    return base64.b64decode(response['content'])


def verify_run(repo,run):
    rid=str(run['id'])
    if run['status']!='completed' or run['conclusion']!='success':raise ValueError('Run has not successfully completed')
    jobs=api(f'repos/{repo}/actions/runs/{rid}/jobs')['jobs']
    required={'Collect genuine current data','Verify saved response and last successful snapshot','Persist snapshots or failure log to GitHub'}
    steps={step['name']:step['conclusion'] for job in jobs if job['name']=='collect' for step in job['steps']}
    if any(steps.get(name)!='success' for name in required):raise ValueError('Collection/verification/persistence step did not succeed')
    entry=json.loads(data_file(repo,f'index/{rid}.json'))
    snapshot=json.loads(data_file(repo,entry['snapshot_path']));raw=data_file(repo,entry['raw_path'])
    if entry['snapshot_id']!=rid or snapshot['snapshot_id']!=rid:raise ValueError('Snapshot/run identity mismatch')
    if hashlib.sha256(raw).hexdigest()!=entry['raw_sha256']:raise ValueError('Raw SHA256 mismatch')
    if parse_payload(raw,snapshot['timestamp'],rid)['items']!=snapshot['items']:raise ValueError('Cleaned data differs from real raw response')
    attempt=json.loads(data_file(repo,f'attempts/{rid}/1.json'))
    if attempt['event']!=run['event']:raise ValueError('Saved event does not match GitHub event')
    if run['event']=='schedule' and attempt['status']!='success':raise ValueError('First scheduled attempt did not succeed; needs explicit retry audit')
    return dict(run_id=int(rid),event=run['event'],url=run['html_url'],created_at=run['created_at'],
                snapshot_timestamp=snapshot['timestamp'],topic_count=len(snapshot['items']),
                ranked_topic_count=snapshot['ranked_topic_count'],raw_sha256=entry['raw_sha256'],
                snapshot_path=entry['snapshot_path'],raw_path=entry['raw_path'],verified=True)


def verify_cloud(repo,manual_id,target=4):
    manual_run=api(f'repos/{repo}/actions/runs/{manual_id}')
    if manual_run['event']!='workflow_dispatch':raise ValueError('Manual validation id is not a workflow_dispatch run')
    manual=verify_run(repo,manual_run)
    runs=api(f'repos/{repo}/actions/workflows/collect-weibo.yml/runs?event=schedule&per_page=100')['workflow_runs']
    eligible=sorted([r for r in runs if r['created_at']>=manual_run['created_at']],key=lambda r:r['created_at'])
    verified=[];errors=[];pending=[];failed=[];skipped=[]
    for run in eligible:
        if run['status']!='completed':pending.append(dict(run_id=run['id'],status=run['status']));continue
        if run['conclusion']=='skipped':skipped.append(run['id']);continue
        if run['conclusion']!='success':failed.append(dict(run_id=run['id'],conclusion=run['conclusion'],url=run['html_url']));continue
        try:verified.append(verify_run(repo,run))
        except (ValueError,KeyError,subprocess.CalledProcessError) as e:errors.append(dict(run_id=run['id'],error=type(e).__name__,message=str(e)[:300]))
        if len(verified)>=target:break
    state=json.loads(data_file(repo,'status.json'))
    return dict(repository=repo,checked_at=now(),manual=manual,scheduled_target=target,
                scheduled_verified=len(verified),scheduled_runs=verified,
                complete=len(verified)>=target and not errors,failed_runs=failed,skipped_runs=skipped,
                pending_runs=pending,verification_errors=errors,
                last_success_at=state.get('last_success_at'),last_attempt_status=state.get('last_attempt_status'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='kruid1-2/memory-tide-data');p.add_argument('--manual-id',type=int,default=38346457723);p.add_argument('--target',type=int,default=4);p.add_argument('--out',default='live/cloud_verification.json');args=p.parse_args()
    report=verify_cloud(args.repo,args.manual_id,args.target);path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
