import asyncio,importlib.util,pathlib,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'conformance_runner.py';s=importlib.util.spec_from_file_location('runner',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Client:
 def __init__(self,status='FINISHED',result='FAILED'):self.calls=[];self.status=status;self.result=result
 async def create_test_plan(self,*a):self.calls.append('plan');return {'id':'plan12345678','name':m.PLANS['certify'],'modules':[{'testModule':'metadata'}]}
 async def create_test_from_plan(self,*a):self.calls.append('create');return {'id':'module12345678','name':'metadata'}
 async def start_test(self,*a):self.calls.append('start')
 async def get_module_info(self,*a):self.calls.append('info');return {'testId':'module12345678','testName':'metadata','status':self.status,'result':self.result}
class Tests(unittest.TestCase):
 def test_real_verdict_not_error(self):
  c=Client();r=asyncio.run(m.Runner(c).run('certify',{},{}));self.assertEqual(c.calls,['plan','create','start','info']);self.assertEqual(r['rows'][0]['result'],'FAILED');self.assertFalse(m.gate(r['rows']))
 def test_waiting_without_adapter_fail_closed(self):
  r=asyncio.run(m.Runner(Client('WAITING',None)).run('certify',{},{}));self.assertEqual(r['rows'][0]['status'],'HARNESS_ERROR');self.assertEqual(r['rows'][0]['harness_category'],'handoff_unavailable')
 def test_interrupted_pass_not_pass(self):
  r=asyncio.run(m.Runner(Client('INTERRUPTED','PASSED')).run('certify',{},{}));self.assertFalse(m.gate(r['rows']))
 def test_selection_validation(self):
  with self.assertRaises(m.HarnessError):asyncio.run(m.Runner(Client()).run('certify',{},{},['absent']))
 def test_secret_exception_never_exposed(self):
  async def failed():raise ValueError('private-token-never-retain')
  with self.assertRaisesRegex(m.HarnessError,'^suite_api_failure$'):asyncio.run(m.Runner(Client()).call(failed))
