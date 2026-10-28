"""Regression: review settings must never reach, or break, the Certify component (run 40643923249: native_result_missing)."""
import asyncio,os,pathlib,sys,types,unittest
S=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(S))
import conformance_runner as cr
from handoffs import Handoffs
ARGS=types.SimpleNamespace(review_window=480,review_dir='/tmp/x',ca_file=None,evidence_dir='/tmp/x',base_url='https://suite:8443')
class T(unittest.TestCase):
 def setUp(self):
  self.old={k:os.environ.pop(k,None) for k in ('GITHUB_TOKEN','GITHUB_RUN_ID','GITHUB_REPOSITORY','GITHUB_REF_NAME')}
 def tearDown(self):
  for k,v in self.old.items():
   if v is not None:os.environ[k]=v
 def test_construction_without_token_does_not_raise_and_certify_unaffected(self):
  h=Handoffs(ARGS,{})  # used to raise review_configuration here and kill the Certify runner before any results file
  self.assertIsNone(h.timeout_for('certify'));self.assertEqual(h.timeout_for('verify'),660)
 def test_verify_without_token_is_a_safe_category_not_a_crash(self):
  h=Handoffs(ARGS,{})
  with self.assertRaises(cr.HarnessError) as e:asyncio.run(h('verify','mod',None))
  self.assertEqual(str(e.exception),'review_configuration')
 def test_certify_manifest_drops_review_keys(self):
  src=(S.parent/'rig-integration/run_combined.py').read_text()
  self.assertIn("if k not in ('review_window','review_dir')",src)
if __name__=='__main__':unittest.main()
