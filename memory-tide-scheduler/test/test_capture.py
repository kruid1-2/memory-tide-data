import importlib.util
import tempfile
import unittest
from pathlib import Path

class CaptureTests(unittest.TestCase):
    def test_reconnections_keep_separate_raw_files_and_exclusive_lock(self):
        path=Path(__file__).resolve().parents[1]/'tools/capture_logs.py'
        self.assertTrue(path.exists(), 'Missing reconnecting capture supervisor')
        spec=importlib.util.spec_from_file_location('capture_logs',path)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            command=['python3','-c','print(\'{"logs":[]}\')']
            mod.capture(root, command, max_sessions=2, retry_seconds=0)
            raws=sorted(root.glob('tail-*.jsonl'))
            self.assertEqual(len(raws),2)
            self.assertTrue(all(p.read_text()=='{"logs":[]}\n' for p in raws))
            with mod.exclusive(root):
                with self.assertRaises(BlockingIOError):
                    with mod.exclusive(root):pass

if __name__=='__main__':unittest.main()
