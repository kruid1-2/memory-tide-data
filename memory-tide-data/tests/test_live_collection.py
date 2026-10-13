import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from memory_tide.live import parse_payload, changes_between, collect_once, verify_store


def response(heat=100):
    return json.dumps({'ok': 1, 'data': {'realtime': [
        {'word': f'话题{i}', 'realpos': i, 'rank': i-1, 'num': heat+i}
        for i in range(1, 51)]}}, ensure_ascii=False).encode()


class LiveCollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def fetch(self, heat=100):return lambda: (response(heat), {'http_status': 200})

    def test_realpos_rank_and_genuine_zero_are_preserved(self):
        raw=json.loads(response());raw['data']['realtime'][0]['num']=0
        data=parse_payload(json.dumps(raw).encode(),'2026-10-13T10:00:00+08:00','run1')
        self.assertEqual(data['items'][0]['rank'],1)
        self.assertEqual(data['items'][0]['heat'],0)
        self.assertEqual(data['timestamp_precision'],'second')
        self.assertNotEqual(data['source'],'bhwa233/weibo-trending-hot-history')

    def test_invalid_response_does_not_fake_snapshot(self):
        result=collect_once(self.root,'fail',1,lambda: (b'<html>Visitor System</html>',{}),timestamp='2026-10-13T10:00:00+08:00')
        self.assertEqual(result['status'],'failed')
        self.assertFalse(list(self.root.glob('snapshots/**/*.json')))
        self.assertIsNone(json.loads((self.root/'status.json').read_text())['last_success_at'])
        self.assertTrue(list(self.root.glob('errors/**/*.bin')))

    def test_retry_is_idempotent_and_raw_is_retained(self):
        first=collect_once(self.root,'run1',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        again=collect_once(self.root,'run1',2,lambda: self.fail('Should not refetch'),timestamp='2026-10-13T11:00:00+08:00')
        self.assertEqual(again['status'],'already_collected')
        self.assertEqual(first['snapshot_id'],again['snapshot_id'])
        self.assertEqual(len(list(self.root.glob('snapshots/**/*.json'))),1)
        verify_store(self.root)

    def test_success_then_failure_keeps_last_success(self):
        collect_once(self.root,'run1',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        before=(self.root/'latest.json').read_bytes()
        collect_once(self.root,'run2',1,lambda: (_ for _ in ()).throw(RuntimeError('timeout')),timestamp='2026-10-13T10:15:00+08:00')
        state=json.loads((self.root/'status.json').read_text())
        self.assertEqual(state['last_success_at'],'2026-10-13T10:00:00+08:00')
        self.assertEqual(state['last_attempt_status'],'failed')
        self.assertEqual(before,(self.root/'latest.json').read_bytes())

    def test_change_uses_actual_seconds_and_missing_stays_null(self):
        a=parse_payload(response(100),'2026-10-13T10:00:00+08:00','a')
        b=parse_payload(response(160),'2026-10-13T10:20:00+08:00','b')
        b['items'][1]['heat']=None
        result=changes_between(a,b)
        self.assertEqual(result['elapsed_seconds'],1200)
        self.assertEqual(result['items'][0]['heat_delta'],60)
        self.assertEqual(result['items'][0]['heat_per_hour'],180)
        self.assertIsNone(result['items'][1]['heat_delta'])
        self.assertEqual(result['items'][1]['metric_basis'],'rank_only')

    def test_missing_topic_is_not_zero(self):
        a=parse_payload(response(),'2026-10-13T10:00:00+08:00','a')
        b=parse_payload(response(),'2026-10-13T10:15:00+08:00','b')
        b['items'][0]['topic_id']='weibo:different';b['items'][0]['title']='替代'
        out=changes_between(a,b)
        self.assertEqual(out['exited_topics'][0]['status'],'not_on_list')
        self.assertIsNone(out['exited_topics'][0]['heat'])

    def test_sources_are_never_mixed(self):
        a=parse_payload(response(),'2026-10-13T10:00:00+08:00','a')
        b=parse_payload(response(),'2026-10-13T10:15:00+08:00','b');a['source']='other'
        result=changes_between(a,b)
        self.assertFalse(result['comparable'])
        self.assertTrue(all(r['heat_delta'] is None for r in result['items']))

    def test_invalid_run_id_and_duplicate_ranks(self):
        with self.assertRaises(ValueError):collect_once(self.root,'../../escape',1,self.fetch())
        raw=json.loads(response());raw['data']['realtime'][1]['realpos']=1
        with self.assertRaises(ValueError):parse_payload(json.dumps(raw).encode(),'2026-10-13T10:00:00+08:00','a')

    def test_retry_recovers_committed_snapshot_after_pointer_failure(self):
        import memory_tide.live as live
        collect_once(self.root,'old',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        original=live.pointer
        def broken(path,value):
            if Path(path).name=='latest_trends.json':raise OSError('simulated write failure')
            return original(path,value)
        with patch.object(live,'pointer',broken):
            result=collect_once(self.root,'new',1,self.fetch(160),timestamp='2026-10-13T10:15:00+08:00')
        self.assertEqual(result['status'],'failed')
        result=collect_once(self.root,'new',2,lambda:self.fail('do not fetch another observation'))
        self.assertEqual(result['status'],'already_collected')
        self.assertEqual(verify_store(self.root)['snapshots_verified'],2)
        self.assertEqual(json.loads((self.root/'status.json').read_text())['last_success_at'],'2026-10-13T10:15:00+08:00')

    def test_old_run_retry_never_rolls_latest_back(self):
        collect_once(self.root,'old',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        collect_once(self.root,'new',1,self.fetch(),timestamp='2026-10-13T10:15:00+08:00')
        collect_once(self.root,'old',2,lambda:self.fail('do not fetch'))
        self.assertEqual(json.loads((self.root/'latest.json').read_text())['snapshot_id'],'new')

    def test_same_second_old_retry_cannot_roll_latest_back(self):
        for run in ['old','new']:
            collect_once(self.root,run,1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        collect_once(self.root,'old',2,lambda:self.fail('do not refetch'))
        self.assertEqual(json.loads((self.root/'latest.json').read_text())['snapshot_id'],'new')

    def test_extreme_finite_changes_are_json_safe(self):
        a=parse_payload(response(),'2026-10-13T10:00:00+08:00','a')
        b=parse_payload(response(),'2026-10-13T10:00:01+08:00','b')
        a['items'][0]['heat']=1e-300;b['items'][0]['heat']=1e308
        json.dumps(changes_between(a,b),allow_nan=False)

    def test_atomic_immutable_publication_does_not_leave_partial_history(self):
        import memory_tide.live as live
        target=self.root/'index/test.json'
        with patch.object(live.os,'link',side_effect=OSError('interrupted before publication')):
            with self.assertRaises(OSError):live.immutable(target,b'{"complete":true}')
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.iterdir()),[])
        live.immutable(target,b'{"complete":true}')
        self.assertEqual(json.loads(target.read_text()),{'complete':True})
        with self.assertRaises(ValueError):live.immutable(target,b'{"changed":true}')
        self.assertEqual(json.loads(target.read_text()),{'complete':True})

    def test_first_committed_index_can_restore_missing_status(self):
        collect_once(self.root,'first',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        for name in ['status.json','latest.json','latest_trends.json']:(self.root/name).unlink()
        result=collect_once(self.root,'first',2,lambda:self.fail('do not refetch committed index'))
        self.assertEqual(result['status'],'already_collected')
        self.assertEqual(verify_store(self.root)['snapshots_verified'],1)

    def test_failed_attempt_replay_restores_status_and_gap(self):
        import memory_tide.live as live
        collect_once(self.root,'old',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        original=live.pointer
        def interrupted(path,value):
            if Path(path).name=='status.json':raise SystemExit('crash after attempt log')
            return original(path,value)
        with patch.object(live,'pointer',interrupted):
            with self.assertRaises(SystemExit):
                collect_once(self.root,'failed',1,lambda:(b'blocked',{}),timestamp='2026-10-13T10:15:00+08:00')
        result=collect_once(self.root,'failed',1,lambda:self.fail('no retry fetch'),outbox=self.root/'outbox')
        self.assertEqual(result['status'],'failed')
        self.assertEqual(json.loads((self.root/'status.json').read_text())['last_attempt_status'],'failed')
        self.assertTrue((self.root/'outbox/attempts/failed/1.json').exists())
        collect_once(self.root,'next',1,self.fetch(),timestamp='2026-10-13T10:30:00+08:00')
        self.assertTrue(json.loads((self.root/'latest_trends.json').read_text())['gap_since_previous'])
        collect_once(self.root,'failed',1,lambda:self.fail('no retry fetch'))
        self.assertEqual(json.loads((self.root/'status.json').read_text())['last_attempt_status'],'success')

    def test_same_second_failed_replay_does_not_override_new_success(self):
        collect_once(self.root,'old',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        collect_once(self.root,'failed',1,lambda:(b'blocked',{}),timestamp='2026-10-13T10:00:00+08:00')
        collect_once(self.root,'new',1,self.fetch(),timestamp='2026-10-13T10:00:00+08:00')
        collect_once(self.root,'failed',1,lambda:self.fail('no refetch'))
        self.assertEqual(json.loads((self.root/'status.json').read_text())['last_attempt_run_id'],'new')


if __name__=='__main__':unittest.main()
