import importlib.util
from pathlib import Path
import subprocess
import unittest
spec=importlib.util.spec_from_file_location('probe',Path(__file__).resolve().parents[1]/'tools/probe.py')
module=importlib.util.module_from_spec(spec)
# Import must not perform HTTP or read a secret.
spec.loader.exec_module(module)

class ProbeTests(unittest.TestCase):
 def test_curl_uses_os_trust_and_keeps_key_off_command_line(self):
  calls=[]
  def run(args,**kwargs):
   calls.append((args,kwargs));return subprocess.CompletedProcess(args,0,b'{"status":"dispatch_accepted"}',b'')
  key='a'*43
  self.assertEqual(module.invoke_probe('https://memory-tide-scheduler.example.workers.dev',key,run)['status'],'dispatch_accepted')
  args,options=calls[0];self.assertNotIn(key,' '.join(args));self.assertNotIn('--insecure',args)
  self.assertIn('Authorization: Bearer '+key,options['input'].decode());self.assertIn('--max-time',args)
 def test_failure_does_not_print_arbitrary_stderr(self):
  def run(args,**kwargs):return subprocess.CompletedProcess(args,60,b'',b'sensitive raw failure')
  with self.assertRaisesRegex(RuntimeError,'curl=60'):module.invoke_probe('https://memory-tide-scheduler.example.workers.dev','a'*43,run)
