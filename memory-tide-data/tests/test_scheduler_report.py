import unittest
from deployment.verify_scheduler import summarize

class ReportTests(unittest.TestCase):
 def test_eight_arbitrary_successes_do_not_replace_a_missing_consecutive_window(self):
  rows=[dict(slot=i*900,verified=True,trigger_source='cloudflare-cron',snapshot_epoch=i*900+10) for i in list(range(7))+[8]]
  r=summarize(0,8,rows,8000)
  self.assertFalse(r['complete']);self.assertEqual(r['missing_windows'],1);self.assertEqual(r['successful_windows'],7)
 def test_dispatch_or_probe_alone_never_counts(self):
  rows=[dict(slot=0,verified=False,trigger_source='cloudflare-cron'),dict(slot=900,verified=True,trigger_source='cloudflare-probe',snapshot_epoch=910)]
  self.assertEqual(summarize(0,2,rows,2000)['successful_windows'],0)
 def test_duplicate_runs_count_once_and_late_data_does_not_count(self):
  rows=[dict(slot=0,verified=True,trigger_source='cloudflare-cron',snapshot_epoch=10)]*2
  rows+=[dict(slot=900,verified=True,trigger_source='cloudflare-cron',snapshot_epoch=1801)]
  r=summarize(0,2,rows,3000);self.assertEqual(r['successful_windows'],1);self.assertFalse(r['complete'])

class ObservationDurationTests(unittest.TestCase):
 def test_last_sample_does_not_finish_a_window_before_it_ends(self):
  rows=[dict(slot=i*900,verified=True,trigger_source='cloudflare-cron',snapshot_epoch=i*900+10) for i in range(8)]
  self.assertFalse(summarize(0,8,rows,6311)['complete'])
 def test_eight_verified_windows_pass_after_observation_end(self):
  rows=[dict(slot=i*900,verified=True,trigger_source='cloudflare-cron',snapshot_epoch=i*900+10) for i in range(8)]
  self.assertTrue(summarize(0,8,rows,7201)['complete'])
