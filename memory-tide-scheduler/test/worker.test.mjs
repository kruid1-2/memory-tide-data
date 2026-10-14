import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker, {dispatch} from '../src/index.mjs';
const when=Date.parse('2026-10-14T06:00:00Z');
const env={GITHUB_DISPATCH_TOKEN:'unit-test-secret-value',DISPATCH_ENABLED:'true',SCHEDULER_ADMIN_KEY:'test-admin'};
function deps(responses) {
 const calls=[],logs=[];let i=0;
 return {calls,logs,now:()=>when+1234,sleep:async()=>{},timeoutMs:2,
  log:x=>logs.push(x),fetch:async(url,opts)=>{calls.push({url,opts});const r=responses[Math.min(i++,responses.length-1)];if(r instanceof Error)throw r;return r;}};
}
test('cron uses fixed GitHub endpoint/ref and stable window; accepted is not collected',async()=>{
 const d=deps([new Response(JSON.stringify({workflow_run_id:123}),{status:200})]);
 const r=await dispatch(when,env,'cloudflare-cron',d);
 assert.equal(r.status,'dispatch_accepted');assert.equal(r.run_id,123);
 const {url,opts}=d.calls[0];assert.equal(url,'https://api.github.com/repos/kruid1-2/memory-tide-data/actions/workflows/collect-weibo.yml/dispatches');
 const body=JSON.parse(opts.body);assert.equal(body.ref,'main');assert.equal(body.inputs.trigger_source,'cloudflare-cron');assert.equal(body.inputs.scheduled_at,'2026-10-14T06:00:00.000Z');
 assert.equal(body.inputs.dispatch_id,'cf-1791957600');assert.equal(opts.redirect,'error');
 assert.ok(!JSON.stringify(d.logs).includes(env.GITHUB_DISPATCH_TOKEN));
});
test('retries 5xx/timeout finitely with same id and never logs raw errors',async()=>{
 const d=deps([new Error('leak '+env.GITHUB_DISPATCH_TOKEN),new Response('secret body',{status:503}),new Response(null,{status:204})]);
 assert.equal((await dispatch(when,env,'cloudflare-cron',d)).status,'dispatch_accepted');assert.equal(d.calls.length,3);
 assert.equal(new Set(d.calls.map(c=>JSON.parse(c.opts.body).inputs.dispatch_id)).size,1);
 assert.ok(!JSON.stringify(d.logs).includes('leak'));assert.ok(!JSON.stringify(d.logs).includes('secret body'));
});
test('permission errors do not retry; exhausted retry fails scheduled task',async()=>{
 const d=deps([new Response('denied',{status:403})]);await assert.rejects(dispatch(when,env,'cloudflare-cron',d),/dispatch_failed/);assert.equal(d.calls.length,1);
 const e=deps([new Response('no',{status:500})]);await assert.rejects(dispatch(when,env,'cloudflare-cron',e));assert.equal(e.calls.length,3);
});
test('network that waits for abort is bounded',async()=>{
 const d=deps([]);d.fetch=(_u,o)=>new Promise((_r,reject)=>o.signal.addEventListener('abort',()=>reject(new Error('timeout'))));
 await assert.rejects(dispatch(when,env,'cloudflare-cron',d));assert.equal(d.logs.filter(x=>x.status==='attempt_failed').length,3);
});
test('disabled, missing secret or stale scheduled events never dispatch',async()=>{
 const d=deps([new Response(null,{status:204})]);
 assert.equal((await dispatch(when,{...env,DISPATCH_ENABLED:'false'},'cloudflare-cron',d)).status,'disabled');
 await assert.rejects(dispatch(when,{...env,GITHUB_DISPATCH_TOKEN:''},'cloudflare-cron',d));
 assert.equal((await dispatch(when-900000,env,'cloudflare-cron',d)).status,'expired');assert.equal(d.calls.length,0);
});
test('no public dispatch endpoint; probe requires separate secret',async()=>{
 assert.equal((await worker.fetch(new Request('https://unit.test/'),env)).status,404);
 assert.equal((await worker.fetch(new Request('https://unit.test/probe',{method:'POST'}),env)).status,401);
});
test('Retry-After beyond retry budget fails without hammering GitHub',async()=>{
 const d=deps([new Response('',{status:429,headers:{'retry-after':'120'}})]);
 await assert.rejects(dispatch(when,env,'cloudflare-cron',d));assert.equal(d.calls.length,1);
});
