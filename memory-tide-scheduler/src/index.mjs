const API='https://api.github.com/repos/kruid1-2/memory-tide-data/actions/workflows/collect-weibo.yml/dispatches';
const WINDOW=900000;
const iso=ms=>new Date(ms).toISOString();
const defaultDeps={fetch:(...args)=>fetch(...args),now:()=>Date.now(),sleep:ms=>new Promise(r=>setTimeout(r,ms)),log:x=>console.log(JSON.stringify(x)),timeoutMs:10000};

export async function dispatch(scheduledTime,env,source='cloudflare-cron',overrides={}) {
 const d={...defaultDeps,...overrides};
 const slot=Math.floor(scheduledTime/WINDOW)*WINDOW;
 const id=source==='cloudflare-cron'?`cf-${slot/1000}`:`probe-${d.now()}-${crypto.randomUUID()}`;
 const base={schema_version:'1',component:'memory-tide-scheduler',trigger_source:source,dispatch_id:id,scheduled_at:iso(slot)};
 const log=(status,fields={})=>d.log({...base,logged_at:iso(d.now()),status,...fields});
 if(env.DISPATCH_ENABLED!=='true'){log('disabled');return {status:'disabled'};}
 if(!env.GITHUB_DISPATCH_TOKEN){log('missing_secret');throw new Error('dispatch_failed: missing Secret');}
 if(d.now()<slot || d.now()>=slot+WINDOW){log('expired');return {status:'expired'};}
 const dispatchedAt=iso(d.now());
 const body=JSON.stringify({ref:'main',inputs:{trigger_source:source,scheduled_at:iso(slot),dispatched_at:dispatchedAt,dispatch_id:id}});
 for(let attempt=1;attempt<=3;attempt++) {
  if(d.now()>=slot+WINDOW){log('expired');throw new Error('dispatch_failed: window expired');}
  const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),d.timeoutMs);
  let response,errorKind='network_or_timeout';
  try {
   response=await d.fetch(API,{method:'POST',redirect:'manual',signal:abort.signal,
    headers:{Authorization:`Bearer ${env.GITHUB_DISPATCH_TOKEN}`,'Content-Type':'application/json',Accept:'application/vnd.github+json','User-Agent':'MEMORY-TIDE-Scheduler/1.0','X-GitHub-Api-Version':'2026-03-10'},body});
   if(response.status===200 || response.status===204) {
    let runId=null;
    if(response.status===200){const result=await response.json();if(Number.isSafeInteger(result.workflow_run_id))runId=result.workflow_run_id;}
    log('dispatch_accepted',{attempt,http_status:response.status,dispatched_at:dispatchedAt,run_id:runId});
    return {status:'dispatch_accepted',dispatch_id:id,run_id:runId};
   }
   errorKind='http';
  } catch (error) {
   // Match only controlled categories; never emit arbitrary messages or headers.
   const message=String(error?.message??'');
   if(/illegal invocation/i.test(message))errorKind='runtime_binding';
   else if(/header|invalid.*character/i.test(message))errorKind='invalid_header';
   else if(/redirect|signal/i.test(message))errorKind='unsupported_option';
   else if(error instanceof ReferenceError)errorKind='runtime_reference';
  }
  finally {clearTimeout(timer);}
  const status=response?.status??null;
  log('attempt_failed',{attempt,http_status:status,error_kind:errorKind,token_has_outer_whitespace:env.GITHUB_DISPATCH_TOKEN!==env.GITHUB_DISPATCH_TOKEN.trim()});
  const limited=status===429 || (status===403 && (response.headers.has('retry-after') || response.headers.get('x-ratelimit-remaining')==='0'));
  const transient=!response || status>=500 || limited;
  let waitSeconds=2**attempt;
  const retryAfter=response?.headers.get('retry-after');
  if(retryAfter){const n=Number(retryAfter);const seconds=Number.isFinite(n)?n:(Date.parse(retryAfter)-d.now())/1000;waitSeconds=Math.max(waitSeconds,seconds);}
  if(!transient || attempt===3 || !Number.isFinite(waitSeconds) || waitSeconds>30)break;
  await d.sleep(waitSeconds*1000);
 }
 log('dispatch_failed');throw new Error('dispatch_failed');
}

export default {
 async scheduled(controller,env,ctx) { await dispatch(controller.scheduledTime,env,'cloudflare-cron'); },
 async fetch(request,env) {
  if(request.method!=='POST' || new URL(request.url).pathname!=='/probe')return new Response('Not found',{status:404});
  if(!env.SCHEDULER_ADMIN_KEY || request.headers.get('Authorization')!==`Bearer ${env.SCHEDULER_ADMIN_KEY}`)return new Response('Unauthorized',{status:401});
  try{return Response.json(await dispatch(Date.now(),env,'cloudflare-probe'));}
  catch{return Response.json({status:'dispatch_failed'},{status:502});}
 }
};
