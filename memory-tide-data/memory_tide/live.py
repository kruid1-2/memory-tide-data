"""One-off official Weibo collection and append-only JSON history for Actions."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote
from .core import clean_title, topic_id, finite_number, time_iso, epoch, now

SOURCE = 'weibo/official-desktop-hotsearch-v1'
ENDPOINT = 'https://weibo.com/ajax/side/hotSearch'
EXPECTED_INTERVAL = 900


def dumps(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def immutable(path, payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    # Link a fully written temporary file atomically; a killed process cannot leave
    # a half-written immutable JSON at the final history path.
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        tmp=Path(f.name);f.write(payload);f.flush();os.fsync(f.fileno())
    try:
        os.link(tmp,path)
    except FileExistsError:
        if path.read_bytes()!=payload:raise ValueError('Refusing to overwrite history: '+str(path))
    finally:
        tmp.unlink(missing_ok=True)


def pointer(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        tmp=Path(f.name);f.write(dumps(data));f.flush();os.fsync(f.fileno())
    tmp.replace(path)


def fetch_payload():
    """curl uses OS CA trust on macOS and Ubuntu; no account/cookie required."""
    with tempfile.TemporaryDirectory() as tmp:
        body=Path(tmp)/'body';headers=Path(tmp)/'headers'
        command=['curl','--silent','--show-error','--location','--fail-with-body',
                 '--connect-timeout','10','--max-time','30','--retry','2','--retry-delay','2',
                 '--header','User-Agent: Mozilla/5.0 MEMORY-TIDE/1.0',
                 '--header','Referer: https://weibo.com/',
                 '--header','Accept: application/json',
                 '--header','Cache-Control: no-cache','--dump-header',str(headers),
                 '--output',str(body),'--write-out','%{http_code}',ENDPOINT]
        result=subprocess.run(command,capture_output=True,check=False)
        payload=body.read_bytes() if body.exists() else b''
        if result.returncode:
            error=RuntimeError(f'HTTP request failed (curl={result.returncode}, HTTP={result.stdout.decode(errors="replace")[-3:]})')
            error.raw_payload=payload
            raise error
        interesting={}
        for line in headers.read_text(errors='replace').splitlines():
            if ':' in line:
                k,v=line.split(':',1)
                if k.lower() in ('date','age','content-type','cache-control'):
                    interesting[k.lower()]=v.strip()
        return payload,dict(http_status=int(result.stdout[-3:]),headers=interesting)


def parse_payload(payload, timestamp, run_id):
    data=json.loads(payload)
    if not isinstance(data,dict) or data.get('ok')!=1 or not isinstance(data.get('data'),dict):
        raise ValueError('Weibo response is not a successful hot-search object')
    realtime=data['data'].get('realtime')
    if not isinstance(realtime,list) or not realtime:raise ValueError('No realtime board returned')
    items=[];seen=set();ranks=set();invalid=0;duplicates=0
    for raw in realtime:
        if not isinstance(raw,dict) or not (title:=clean_title(raw.get('word'))):
            invalid+=1;continue
        tid=topic_id(title)
        if tid in seen:
            duplicates+=1;continue
        seen.add(tid);quality=[];ad=bool(raw.get('is_ad') or raw.get('topic_ad'))
        rank=raw.get('realpos')
        # rank is a zero-based row/display index including ads; realpos is board rank.
        if isinstance(rank,bool) or not isinstance(rank,int) or not 1<=rank<=50:
            rank=None;quality.append('missing_rank')
        elif not ad:
            if rank in ranks:raise ValueError('Duplicate realpos in official board')
            ranks.add(rank)
        heat=finite_number(raw.get('num'))
        if heat is None or heat<0:heat=None;quality.append('missing_or_invalid_heat')
        if ad:quality.append('advertisement')
        if heat is not None and heat>100_000_000:quality.append('extreme_heat_review')
        query=raw.get('word_scheme') if isinstance(raw.get('word_scheme'),str) else title
        items.append(dict(topic_id=tid,title=title,rank=rank,heat=heat,raw_heat=finite_number(raw.get('num')),
                          timestamp=time_iso(timestamp),platform='weibo',source=SOURCE,
                          url='https://s.weibo.com/weibo?q='+quote(query,safe=''),is_ad=ad,quality=quality))
    if len(ranks)<40:raise ValueError(f'Insufficient board coverage: {len(ranks)} valid ranks (minimum 40)')
    govs=data['data'].get('hotgovs')
    if not isinstance(govs,list):govs=[data['data'].get('hotgov')]
    for raw in govs:
        if not isinstance(raw,dict):continue
        title=clean_title(raw.get('word',raw.get('name')))
        if not title or topic_id(title) in seen:continue
        seen.add(topic_id(title))
        items.append(dict(topic_id=topic_id(title),title=title,rank=None,heat=None,raw_heat=None,
                          timestamp=time_iso(timestamp),platform='weibo',source=SOURCE,
                          url='https://s.weibo.com/weibo?q='+quote(title,safe=''),is_ad=False,
                          quality=['pinned_topic','unranked','missing_heat']))
    return dict(schema_version='1.0',snapshot_id=run_id,source=SOURCE,source_url=ENDPOINT,platform='weibo',
                timestamp=time_iso(timestamp),timezone='Asia/Shanghai',timestamp_precision='second',
                timestamp_basis='client_response_received_at; server observation time unknown',
                expected_interval_seconds=EXPECTED_INTERVAL,complete_rank_coverage=len(ranks)==50,
                ranked_topic_count=len(ranks),invalid_rows=invalid,duplicate_rows=duplicates,
                quality=[] if len(ranks)==50 else ['partial_rank_coverage'],items=items)


def changes_between(previous,current,had_failed_attempt=False):
    comparable=bool(previous and previous.get('source')==current['source'])
    dt=epoch(current['timestamp'])-epoch(previous['timestamp']) if comparable else None
    comparable=bool(comparable and dt and dt>0)
    before={r['topic_id']:r for r in previous['items'] if not r['is_ad']} if comparable else {}
    gap=bool(comparable and (dt>EXPECTED_INTERVAL*2 or had_failed_attempt))
    items=[]
    for row in current['items']:
        if row['is_ad']:continue
        old=before.get(row['topic_id']);delta=pct=rate=rank_delta=None;basis='unavailable';phase='unknown'
        if old:
            if row['heat'] is not None and old['heat'] is not None:
                delta=finite_number(row['heat']-old['heat'])
                pct=finite_number(delta/old['heat']*100) if old['heat']>0 and delta is not None else None
                rate=finite_number(delta*(3600/dt)) if delta is not None else None
                basis='observed_heat_endpoints'
                phase='rising' if delta>0 else 'fading' if delta<0 else 'stable'
            if row['rank'] is not None and old['rank'] is not None:rank_delta=old['rank']-row['rank']
            if delta is None and rank_delta is not None:
                basis='rank_only';phase='rank_rising' if rank_delta>0 else 'rank_fading' if rank_delta<0 else 'rank_stable'
        quality=list(row['quality'])
        if gap:quality.append('gap_since_previous_success')
        if not old:quality.append('no_comparable_previous_topic')
        items.append(dict(row,previous_heat=old['heat'] if old else None,heat_delta=delta,heat_pct=pct,
                          heat_per_hour=rate,rank_delta=rank_delta,metric_basis=basis,phase=phase,quality=quality))
    current_ids={r['topic_id'] for r in current['items']}
    exited=[dict(topic_id=r['topic_id'],title=r['title'],heat=None,rank=None,source=current['source'],
                 timestamp=current['timestamp'],status='not_on_list' if current['complete_rank_coverage'] else 'unknown_partial_snapshot')
            for r in before.values() if r['topic_id'] not in current_ids]
    rising=sorted([r for r in items if r['heat_per_hour'] is not None and r['heat_per_hour']>0],key=lambda r:r['heat_per_hour'],reverse=True)
    fading=sorted([r for r in items if r['heat_per_hour'] is not None and r['heat_per_hour']<0],key=lambda r:r['heat_per_hour'])
    return dict(schema_version='1.0',source=current['source'],timestamp=current['timestamp'],
                previous_snapshot_id=previous['snapshot_id'] if comparable else None,elapsed_seconds=dt,
                comparable=comparable,gap_since_previous=gap,
                semantics='Endpoint differences across actual receive timestamps; no continuous-growth or off-list-zero inference',
                items=items,rising_topics=rising,fading_topics=fading,exited_topics=exited)


def safe_run_id(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value):raise ValueError('Invalid run id')
    return value


def collect_once(root,run_id,attempt=1,fetcher=fetch_payload,timestamp=None,event='local',outbox=None):
    run_id=safe_run_id(run_id)
    if not isinstance(attempt,int) or attempt<1:raise ValueError('Invalid attempt')
    root=Path(root);root.mkdir(parents=True,exist_ok=True);written=[]
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        index=root/'index'/f'{run_id}.json'
        if index.exists():
            existing=load(index)
            state=load(root/'status.json') if (root/'status.json').exists() else {}
            current_time=state.get('last_success_at')
            # Immutable index is the commit record. Repair derived pointers after
            # interruption, while rerunning an older workflow never rolls them back.
            newer=(not current_time or epoch(existing['timestamp'])>epoch(current_time))
            tied_next=bool(current_time and epoch(existing['timestamp'])==epoch(current_time)
                           and (state.get('last_success_run_id')==run_id
                                or existing.get('previous_snapshot_id')==state.get('last_success_run_id')))
            if newer or tied_next:
                latest=load(root/'latest.json') if (root/'latest.json').exists() else {}
                needs_repair=(state.get('last_success_run_id')!=run_id or latest.get('snapshot_id')!=run_id
                              or not (root/'latest_trends.json').exists()
                              or (state.get('last_attempt_status')=='failed' and state.get('last_attempt_run_id')==run_id))
                if needs_repair:
                    payload=(root/existing['raw_path']).read_bytes()
                    snapshot=load(root/existing['snapshot_path']);trends=load(root/existing['trend_path'])
                    if hashlib.sha256(payload).hexdigest()!=existing['raw_sha256']:raise ValueError('Committed raw checksum mismatch')
                    if parse_payload(payload,snapshot['timestamp'],run_id)['items']!=snapshot['items']:
                        raise ValueError('Committed snapshot is inconsistent')
                    pointer(root/'latest.json',existing);pointer(root/'latest_trends.json',trends)
                    state.update(schema_version='1.0',source=SOURCE,expected_interval_seconds=EXPECTED_INTERVAL,
                                 last_success_at=existing['timestamp'],last_snapshot_path=existing['snapshot_path'],
                                 last_success_run_id=run_id,consecutive_failures=0,last_error=None,
                                 last_attempt_at=now(),last_attempt_status='already_collected',last_attempt_run_id=run_id,
                                 last_attempt_number=attempt)
                    pointer(root/'status.json',state)
                    if outbox:
                        for path in [existing['raw_path'],existing['snapshot_path'],existing['trend_path'],str(index.relative_to(root)),
                                     'latest.json','latest_trends.json','status.json']:
                            dest=Path(outbox)/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/path,dest)
            return dict(status='already_collected',snapshot_id=run_id,snapshot_path=existing['snapshot_path'])
        attempt_path=root/'attempts'/run_id/f'{attempt}.json'
        if attempt_path.exists():
            result=load(attempt_path)
            state=load(root/'status.json') if (root/'status.json').exists() else {}
            when=result.get('attempt_at',result['finished_at'])
            current_time=state.get('last_attempt_at')
            same=(state.get('last_attempt_run_id')==run_id and state.get('last_attempt_number')==attempt)
            current_key=f"{state.get('last_attempt_run_id')}/{state.get('last_attempt_number',1)}"
            newer=not current_time or epoch(when)>epoch(current_time)
            tied_next=bool(current_time and epoch(when)==epoch(current_time)
                           and (same or result.get('previous_attempt_key')==current_key))
            if result['status']=='failed' and (newer or tied_next):
                state.update(schema_version='1.0',source=SOURCE,expected_interval_seconds=EXPECTED_INTERVAL,
                             last_attempt_at=when,last_attempt_status='failed',last_attempt_run_id=run_id,
                             last_attempt_number=attempt,last_error=result['error'],
                             consecutive_failures=state.get('consecutive_failures',0)+(0 if same else 1))
                state.setdefault('last_success_at',None);pointer(root/'status.json',state)
            if outbox:
                paths=[str(attempt_path.relative_to(root)),'status.json']
                if result.get('error',{}).get('raw_path'):paths.append(result['error']['raw_path'])
                for path in paths:
                    dest=Path(outbox)/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/path,dest)
            return result
        state=load(root/'status.json') if (root/'status.json').exists() else {}
        started_at=now();payload=None;received_at=None
        result=dict(schema_version='1.0',source=SOURCE,run_id=run_id,attempt=attempt,event=event,
                    started_at=started_at,status='failed',snapshot_id=None,error=None,
                    previous_attempt_key=f"{state.get('last_attempt_run_id')}/{state.get('last_attempt_number',1)}")
        try:
            payload,http_info=fetcher();received_at=time_iso(timestamp or now())
            snapshot=parse_payload(payload,received_at,run_id)
            date=received_at[:10];key=received_at[11:19].replace(':','')+'_'+run_id
            raw_path=Path('raw')/date/(key+'.json');snapshot_path=Path('snapshots')/date/(key+'.json')
            sha=hashlib.sha256(payload).hexdigest()
            snapshot.update(raw_path=str(raw_path),raw_sha256=sha,http=http_info)
            previous=load(root/state['last_snapshot_path']) if state.get('last_snapshot_path') else None
            trends=changes_between(previous,snapshot,state.get('last_attempt_status')=='failed')
            trend_path=Path('trends')/date/(key+'.json')
            # Immutable records and raw evidence are written before any mutable pointer.
            for path,data in [(raw_path,payload),(snapshot_path,dumps(snapshot)),(trend_path,dumps(trends))]:
                immutable(root/path,data);written.append(path)
            entry=dict(snapshot_id=run_id,timestamp=received_at,snapshot_path=str(snapshot_path),
                       raw_path=str(raw_path),raw_sha256=sha,trend_path=str(trend_path),source=SOURCE,
                       previous_snapshot_id=previous['snapshot_id'] if previous else None)
            immutable(index,dumps(entry));written.append(index.relative_to(root))
            pointer(root/'latest.json',entry);pointer(root/'latest_trends.json',trends)
            written.extend([Path('latest.json'),Path('latest_trends.json')])
            state.update(last_success_at=received_at,last_snapshot_path=str(snapshot_path),
                         last_success_run_id=run_id,consecutive_failures=0)
            result.update(status='success',snapshot_id=run_id,snapshot_path=str(snapshot_path),
                          raw_path=str(raw_path),raw_sha256=sha,topic_count=len(snapshot['items']),
                          ranked_topic_count=snapshot['ranked_topic_count'],received_at=received_at)
        except Exception as exc:
            if payload is None:payload=getattr(exc,'raw_payload',None)
            # Do not log response bodies/cookies in GitHub logs; retain response bytes separately.
            result['error']=dict(type=type(exc).__name__,message=str(exc)[:400])
            state['consecutive_failures']=state.get('consecutive_failures',0)+1
            if payload is not None:
                path=Path('errors')/run_id/f'{attempt}.bin';immutable(root/path,payload);written.append(path)
                result['error']['raw_path']=str(path)
        result['finished_at']=now();result['attempt_at']=time_iso(timestamp or result['finished_at'])
        immutable(attempt_path,dumps(result));written.append(attempt_path.relative_to(root))
        state.update(schema_version='1.0',source=SOURCE,expected_interval_seconds=EXPECTED_INTERVAL,
                     last_attempt_at=result['attempt_at'],last_attempt_status=result['status'],
                     last_attempt_run_id=run_id,last_attempt_number=attempt,last_error=result['error'])
        state.setdefault('last_success_at',None)
        pointer(root/'status.json',state);written.append(Path('status.json'))
        if outbox:
            for path in written:
                target=Path(outbox)/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/path,target)
        return result


def verify_store(root,all_snapshots=True):
    root=Path(root);state=load(root/'status.json');checked=0
    files=list((root/'index').glob('*.json')) if all_snapshots else ([root/'index'/(state['last_success_run_id']+'.json')] if state.get('last_success_run_id') else [])
    for path in files:
        entry=load(path);snapshot=load(root/entry['snapshot_path']);payload=(root/entry['raw_path']).read_bytes()
        if hashlib.sha256(payload).hexdigest()!=entry['raw_sha256']:raise ValueError('Raw SHA256 mismatch')
        expected=parse_payload(payload,snapshot['timestamp'],snapshot['snapshot_id'])
        if expected['items']!=snapshot['items']:raise ValueError('Snapshot differs from retained raw response')
        if not (root/entry['trend_path']).exists():raise ValueError('Missing immutable trend file')
        checked+=1
    if state.get('last_success_run_id'):
        latest=load(root/'latest.json')
        if latest['snapshot_id']!=state['last_success_run_id']:raise ValueError('Latest pointer disagrees with status')
    return dict(status='ok',snapshots_verified=checked,last_success_at=state.get('last_success_at'),
                last_attempt_status=state['last_attempt_status'])


def main():
    p=argparse.ArgumentParser(description='MEMORY TIDE append-only live JSON collection')
    sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('collect');c.add_argument('--root',default='live/observations');c.add_argument('--run-id',default='local-'+uuid.uuid4().hex)
    c.add_argument('--attempt',type=int,default=1);c.add_argument('--event',default='local');c.add_argument('--outbox')
    c=sub.add_parser('verify');c.add_argument('--root',default='live/observations');c.add_argument('--last-only',action='store_true')
    args=p.parse_args()
    if args.command=='verify':result=verify_store(args.root,not args.last_only)
    else:result=collect_once(args.root,args.run_id,args.attempt,event=args.event,outbox=args.outbox)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    if result['status']=='failed':raise SystemExit(1)


if __name__=='__main__':main()
