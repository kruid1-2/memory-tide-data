import json
from pathlib import Path
import tempfile
import unittest
from deployment.normalize_worker_logs import normalize

class CaptureTests(unittest.TestCase):
 def test_preserves_complete_event_before_corrupt_disconnect_text(self):
  event=dict(component='memory-tide-scheduler',status='dispatch_accepted',trigger_source='cloudflare-cron',dispatch_id='cf-1',run_id=1)
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'raw';source.write_text(json.dumps({'logs':[{'message':[json.dumps(event)]}],'event':{'request':{'headers':{'authorization':'private'}}}})+'\nstart a new session."\n')
   out=Path(d)/'normalized';report=normalize([source],out)
   saved=[json.loads(x) for x in out.read_text().splitlines()]
   self.assertEqual(len(saved),1);self.assertEqual(saved[0]['run_id'],1)
   self.assertTrue(report['capture_warnings']);self.assertNotIn('private',out.read_text())
 def test_partial_event_never_becomes_complete_and_duplicates_count_once(self):
  event=dict(component='memory-tide-scheduler',status='dispatch_accepted',trigger_source='cloudflare-cron',dispatch_id='cf-1',run_id=1)
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a';b=Path(d)/'b';a.write_text(json.dumps(event)+'\n');b.write_text(json.dumps(event)+'\n{"component":')
   out=Path(d)/'out';r=normalize([a,b],out)
   self.assertEqual(len(out.read_text().splitlines()),1);self.assertTrue(r['capture_warnings'])
