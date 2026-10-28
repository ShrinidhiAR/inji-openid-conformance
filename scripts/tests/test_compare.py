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
