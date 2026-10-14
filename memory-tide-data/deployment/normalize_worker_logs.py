"""Retain complete genuine console events from tail captures without altering raw logs.

On corrupt/truncated input, stop at that boundary and report it explicitly. Never
invent or repair an event. HTTP request metadata and credentials are not copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

FIELDS={'schema_version','component','trigger_source','dispatch_id','scheduled_at','dispatched_at',
        'logged_at','status','attempt','http_status','error_kind','run_id','token_has_outer_whitespace'}


def normalize(sources,output):
    decoder=json.JSONDecoder();events=[];seen=set();warnings=[];captures=[]
    for source in sources:
        source=Path(source);raw=source.read_bytes();text=raw.decode('utf-8');offset=0;count=0
        while offset<len(text):
            if text[offset].isspace():offset+=1;continue
            start=offset
            try:value,end=decoder.raw_decode(text,offset)
            except json.JSONDecodeError:
                warnings.append(dict(file=source.name,first_unparsed_character=offset,
                                     remaining_characters=len(text)-offset,reason='Non-JSON or incomplete capture; no events beyond this boundary certified'))
                break
            offset=end;count+=1;messages=[]
            if isinstance(value,dict):
                if value.get('component')=='memory-tide-scheduler':messages.append(value)
                for log in value.get('logs',[]):
                    for message in log.get('message',[]):
                        if not isinstance(message,str):continue
                        try:item=json.loads(message)
                        except json.JSONDecodeError:continue
                        if isinstance(item,dict) and item.get('component')=='memory-tide-scheduler':messages.append(item)
            for message in messages:
                entry={k:v for k,v in message.items() if k in FIELDS}
                identity=json.dumps(entry,sort_keys=True)
                if identity in seen:continue
                seen.add(identity)
                entry['_capture']=dict(file=source.name,record_start_character=start,
                                       record_sha256=hashlib.sha256(text[start:end].encode()).hexdigest())
                events.append(entry)
        captures.append(dict(file=source.name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),complete_json_records=count))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent,delete=False,mode='w') as f:
        tmp=Path(f.name)
        for event in events:f.write(json.dumps(event,ensure_ascii=False)+'\n')
    tmp.replace(output)
    return dict(events=len(events),captures=captures,capture_warnings=warnings,
                semantics='Only complete genuine console records retained. Capture warnings do not certify missing events or sampling success.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('sources',nargs='+');p.add_argument('--out',required=True);p.add_argument('--report',required=True);a=p.parse_args()
    report=normalize(a.sources,a.out);Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
