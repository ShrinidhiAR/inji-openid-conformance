import importlib.util,pathlib,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'compare_results.py';s=importlib.util.spec_from_file_location('c',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def doc(status,result):return {'certify':[{'module':'a','status':status,'result':result}],'verify':[]}
class T(unittest.TestCase):
 def test_change_and_classification(self):
  r=c.compare(doc('FINISHED','FAILED'),doc('FINISHED','PASSED'))[0];self.assertEqual((r['change'],r['classification']),('changed','passed'))
 def test_expected_only_when_user_lists_exact_result(self):
  exp=[{'component':'certify','module':'a','result':'FAILED'}]
  self.assertEqual(c.compare(doc('FINISHED','FAILED'),doc('FINISHED','FAILED'),exp)[0]['classification'],'expected_failure')
  self.assertEqual(c.compare(doc('FINISHED','FAILED'),doc('INTERRUPTED','FAILED'),exp)[0]['classification'],'expected_failure')
  self.assertEqual(c.compare(doc('FINISHED','FAILED'),doc('FINISHED','REVIEW'),exp)[0]['classification'],'unexpected_not_passed')
 def test_default_never_expected_and_missing_detected(self):
  r=c.compare(doc('FINISHED','FAILED'),{'certify':[],'verify':[]});self.assertEqual((r[0]['change'],r[0]['classification']),('removed','unexpected_not_passed'))

def combined(cr,vr,selected=('certify','verify')):
 return {'selected':list(selected),'certify':cr,'verify':vr}
class G(unittest.TestCase):
 def test_green_on_exact_match(self):
  exp=[{'component':'certify','module':'m','result':'FAILED','status':'INTERRUPTED'}]
  d=combined([{'module':'m','status':'INTERRUPTED','result':'FAILED'}],[])
  self.assertTrue(c.gate(d,exp)['matches'])
 def test_unexpected_result_is_red(self):
  exp=[{'component':'certify','module':'m','result':'FAILED','status':'INTERRUPTED'}]
  d=combined([{'module':'m','status':'FINISHED','result':'FAILED'}],[])
  self.assertFalse(c.gate(d,exp)['matches'])
 def test_fixed_module_is_stale_baseline_red(self):
  exp=[{'component':'certify','module':'m','result':'FAILED'}]
  d=combined([{'module':'m','status':'FINISHED','result':'PASSED'}],[])
  v=c.gate(d,exp);self.assertFalse(v['matches']);self.assertEqual(v['expected_but_not_observed'][0]['module'],'m')
 def test_scope_limited_to_selected_components(self):
  exp=[{'component':'certify','module':'m','result':'FAILED'},{'component':'verify','module':'v','result':None,'status':'HARNESS_ERROR'}]
  d=combined([{'module':'m','status':'INTERRUPTED','result':'FAILED'}],[],selected=('certify',))
  self.assertTrue(c.gate(d,exp)['matches'])
 def test_review_is_not_baselines_green(self):
  exp=[{'component':'certify','module':'m','result':'FAILED','status':'INTERRUPTED'},{'component':'verify','module':'v','result':None,'status':'HARNESS_ERROR'}]
  d=combined([{'module':'m','status':'INTERRUPTED','result':'FAILED'}],[{'module':'oid4vp-1final-verifier-happy-flow','status':'FINISHED','result':'REVIEW'}])
  v=c.gate(d,exp);self.assertFalse(v['matches']);self.assertEqual(v['unexpected_not_passed'][0]['observed_result'],'REVIEW')
if __name__=='__main__':unittest.main()
