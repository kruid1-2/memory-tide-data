import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from deployment.scheduled_collect import run_collection
from memory_tide.live import immutable,dumps

SLOT='2026-10-14T06:00:00Z'
NOW='2026-10-14T06:01:00Z'
def context(run='100',source='cloudflare-cron',planned=SLOT):
 return dict(run_id=run,attempt=1,event='workflow_dispatch',trigger_source=source,scheduled_at=planned,dispatched_at='2026-10-14T06:00:01Z',dispatch_id='cf-1791957600',workflow_created_at='2026-10-14T06:00:02Z',workflow_started_at=NOW)

def collector(root,run_id,attempt,**kwargs):
 root=Path(root);entry=dict(snapshot_id=run_id,timestamp=NOW,raw_sha256='test-fixture-only',snapshot_path='fixture')
 immutable(root/'index'/f'{run_id}.json',dumps(entry))
 return dict(status='success',snapshot_id=run_id)

class GateTests(unittest.TestCase):
 def test_cloudflare_then_native_one_real_collection(self):
  with tempfile.TemporaryDirectory() as d:
   with patch('deployment.scheduled_collect.collect_once',side_effect=collector) as c:
    a=run_collection(d,context(),clock=lambda:NOW)
    ctx=context('101');ctx.update(event='schedule',trigger_source='manual',scheduled_at='',dispatch_id='')
    b=run_collection(d,ctx,clock=lambda:NOW)
    self.assertEqual(a['status'],'success');self.assertEqual(b['status'],'duplicate_window');self.assertEqual(c.call_count,1)
 def test_native_then_cloudflare_and_existing_old_index(self):
  with tempfile.TemporaryDirectory() as d:
   immutable(Path(d)/'index'/'old.json',dumps(dict(snapshot_id='old',timestamp=NOW)))
   with patch('deployment.scheduled_collect.collect_once') as c:
    b=run_collection(d,context(),clock=lambda:NOW)
    self.assertEqual(b['canonical_run_id'],'old');c.assert_not_called()
 def test_expired_and_malformed_dispatch_never_collect(self):
  with tempfile.TemporaryDirectory() as d,patch('deployment.scheduled_collect.collect_once') as c:
   self.assertEqual(run_collection(d,context(),clock=lambda:'2026-10-14T06:16:00Z')['status'],'expired_window')
   x=context('102');x['dispatch_id']='wrong'
   with self.assertRaises(ValueError):run_collection(d,x,clock=lambda:NOW)
   c.assert_not_called()
 def test_failed_collection_does_not_consume_window(self):
  with tempfile.TemporaryDirectory() as d:
   with patch('deployment.scheduled_collect.collect_once',return_value={'status':'failed'}):
    run_collection(d,context(),clock=lambda:NOW)
   with patch('deployment.scheduled_collect.collect_once',side_effect=collector) as c:
    self.assertEqual(run_collection(d,context('101'),clock=lambda:NOW)['status'],'success');self.assertEqual(c.call_count,1)
 def test_same_run_retry_repairs_claim_and_returns_committed_result(self):
  with tempfile.TemporaryDirectory() as d:
   with patch('deployment.scheduled_collect.collect_once',side_effect=collector):run_collection(d,context(),clock=lambda:NOW)
   with patch('deployment.scheduled_collect.collect_once') as c:
    self.assertEqual(run_collection(d,context(),clock=lambda:NOW)['status'],'success');c.assert_not_called()
 def test_manual_source_distinguished(self):
  with tempfile.TemporaryDirectory() as d,patch('deployment.scheduled_collect.collect_once',side_effect=collector):
   x=context(source='manual');x.update(scheduled_at='',dispatch_id='')
   self.assertEqual(run_collection(d,x,clock=lambda:NOW)['trigger_source'],'manual')
