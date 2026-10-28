import importlib.util,json,pathlib,tempfile,types,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'review_gate.py';s=importlib.util.spec_from_file_location('g',p);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
def ns(**k):return types.SimpleNamespace(**{'dir':None,'exit_file':None,'log':None,'timeout':10,'interval':1,**k})
class T(unittest.TestCase):
 def test_check_dir_exact_pair_only(self):
  with tempfile.TemporaryDirectory() as t:
   d=pathlib.Path(t);(d/'manifest.json').write_text(json.dumps({'test_id':'module12345678'}));(d/'module12345678-verify-result.png').write_bytes(b'x')
   self.assertEqual(g.check_dir(ns(dir=t)),0);(d/'extra.json').write_text('{}');self.assertEqual(g.check_dir(ns(dir=t)),1)
 def test_wait_exit_prints_only_known_prefixes_and_code(self):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);(t/'e').write_text('1');(t/'l').write_text('LIFECYCLE []\nsecret=abc\nHTTP_EVIDENCE {}\n')
   import io,contextlib;b=io.StringIO()
   with contextlib.redirect_stdout(b):code=g.wait_exit(ns(exit_file=str(t/'e'),log=str(t/'l')))
   self.assertEqual(code,1);self.assertNotIn('secret',b.getvalue());self.assertIn('LIFECYCLE',b.getvalue())
 def test_wait_pending_false_when_process_exits_without_request(self):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);(t/'e').write_text('0');import io,contextlib;b=io.StringIO()
   with contextlib.redirect_stdout(b):g.wait_pending(ns(dir=str(t/'r'),exit_file=str(t/'e')))
   self.assertIn('pending=false',b.getvalue())
 def test_wait_pending_true_when_manifest_written(self):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);(t/'r').mkdir();(t/'r'/'manifest.json').write_text('{}');import io,contextlib;b=io.StringIO()
   with contextlib.redirect_stdout(b):g.wait_pending(ns(dir=str(t/'r'),exit_file=str(t/'e')))
   self.assertIn('pending=true',b.getvalue())
