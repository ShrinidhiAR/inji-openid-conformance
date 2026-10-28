import pathlib,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];S=str(ROOT/'run-full-stack-conformance.sh')
def run(*a):return subprocess.run(['bash',S,*a],capture_output=True,text=True,env={'PATH':'/usr/bin:/bin'})
class Tests(unittest.TestCase):
 def test_syntax(self):self.assertEqual(subprocess.run(['bash','-n',S]).returncode,0)
 def test_requires_explicit_runtime_approval(self):
  r=run('--combined');self.assertEqual(r.returncode,2);self.assertIn('--approve-runtime',r.stderr)
 def test_single_component_fails_closed(self):
  for c in ('certify','verify'):self.assertEqual(run('--component',c,'--approve-runtime').returncode,2)
 def test_no_mode_rejected(self):self.assertEqual(run('--approve-runtime').returncode,2)
 def test_calls_actual_orchestrator_and_cleanup(self):
  t=(ROOT/'run-full-stack-conformance.sh').read_text();self.assertIn('rig-integration/run_combined.py',t);self.assertIn('fallback_cleanup.py',t);self.assertIn('audit_evidence.py',t)
