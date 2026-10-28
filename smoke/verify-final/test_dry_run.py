"""Fake-suite end-to-end dry run of Runner + Verify adapter + review window. Not live product evidence."""
import asyncio,hashlib,importlib.util,json,pathlib,sys,tempfile,unittest,httpx
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(HERE))
import review,adapter,contract
s=importlib.util.spec_from_file_location('runner',ROOT/'scripts/conformance_runner.py');runner=importlib.util.module_from_spec(s);s.loader.exec_module(runner)
PNG=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(1200).to_bytes(4,'big')+(900).to_bytes(4,'big')+b'\x08\x02\x00\x00\x00'+b'x'*50
MOD='module12345678'
class Suite:
 def __init__(self):self.state='WAITING';self.uploaded=[];self.tx=None;self.has_placeholder=True
 def respond(self,req):
  p=req.url.path
  if p.startswith('/api/runner/'):return httpx.Response(200,json={'id':MOD,'name':'oid4vp-1final-verifier-happy-flow','browser':{'uriInputRequests':[{'submitUrl':'https://suite:8443/test/'+MOD+'/authorize'}]}})
  if p.endswith('/v2/vp-request'):
   self.tx=json.loads(req.content)['transactionId'];return httpx.Response(201,json={'transactionId':self.tx,'requestId':'req_12345678-abcd-1234-abcd-123456789012','authorizationDetails':{'clientId':contract.CLIENT,'responseUri':contract.RESPONSE,'responseMode':'direct_post','responseType':'vp_token','dcqlQuery':contract.DCQL,'nonce':'n'*20,'responseCodeValidationRequired':False}})
  if p.endswith('/authorize'):return httpx.Response(200,text='ok')
  if '/v2/vp-results/' in p:return httpx.Response(200,json={'transactionId':self.tx,'allChecksSuccessful':True,'credentialResults':[{'allChecksSuccessful':True,'schemaAndSignatureCheck':{'valid':True},'expiryCheck':{'valid':True},'holderProofCheck':{'valid':True},'statusCheck':[]}]})
  if p=='/api/info/'+MOD:return httpx.Response(200,json={'testId':MOD,'status':self.state})
  if p=='/api/log/'+MOD:return httpx.Response(200,json=[{'src':'X','result':'SUCCESS'}]+([{'upload':'ph_abcdef','result':'REVIEW'}] if self.has_placeholder else []))
  if p=='/api/log/'+MOD+'/images/ph_abcdef':
   if self.state!='WAITING':return httpx.Response(200)
   self.uploaded.append(req.content);self.has_placeholder=False;self.state='FINISHED';return httpx.Response(200,json={'img':req.content.decode(),'time':1})
  return httpx.Response(500)
class Client:
 def __init__(self,suite):self.suite=suite;self.waited=0
 async def create_test_plan(self,*a):return {'id':'plan12345678','name':runner.PLANS['verify'],'modules':[{'testModule':'oid4vp-1final-verifier-happy-flow'}]}
 async def create_test_from_plan(self,*a):return {'id':MOD,'name':'oid4vp-1final-verifier-happy-flow'}
 async def start_test(self,*a):pass
 async def get_module_info(self,*a):return {'testId':MOD,'testName':'oid4vp-1final-verifier-happy-flow','status':self.suite.state,'result':'REVIEW' if self.suite.state=='FINISHED' else None}
 async def get_test_log(self,*a):return []
def dry(approver,window=300,local=False):
 async def execute():
  suite=Suite();clock=[10_000];ticks=[0];tmp=pathlib.Path(tempfile.mkdtemp());rv=tmp/'review';ev=tmp/'ev';ap=tmp/'approvals'
  if local:rv.mkdir(mode=0o700);ap.mkdir(mode=0o700)
  async def heartbeat():
   while True:await asyncio.sleep(0.001);ticks[0]+=1
  async def sleep(sec):
   clock[0]+=sec;await asyncio.sleep(0.005)
   if local and clock[0]>=10_030 and not list(ap.iterdir()):review.write_local_approval(rv,ap,hashlib.sha256(PNG).hexdigest(),clock[0])   # the second-terminal step, with the typed hash
  polls=[0]
  async def source(path):
   polls[0]+=1;return approver(json.loads((rv/'manifest.json').read_text()),polls[0],clock[0])
  cfg={'dir':rv,'window':window,'run_id':'777','source':review.local_source(ap) if local else source,'clock':lambda:clock[0],'sleep':sleep,'interval':15}
  bridge=adapter.Adapter(True,ev,review=cfg);await bridge.http.aclose();bridge.http=httpx.AsyncClient(transport=httpx.MockTransport(suite.respond))
  async def capture(html,module):(ev/(module+'-verify-result.png')).write_bytes(PNG)
  bridge.capture=capture
  class H:
   timeout=window+180
   async def __call__(self,component,module,client):await bridge(component,module,client)
  hb=asyncio.create_task(heartbeat())
  try:result=await runner.Runner(Client(suite),timeout=30,handoff=H()).run('verify',{},{})
  finally:hb.cancel();await bridge.close()
  return result,suite,ticks[0],polls[0],rv,ev
 return asyncio.run(execute())
def ok(m,n,now):return {'schema':1,'run_id':m['run_id'],'test_id':m['test_id'],'png_sha256':m['png_sha256'],'approved_at':m['created_at']+1,'decision':'approve_faithful_view'} if n>=3 else None
class T(unittest.TestCase):
 def test_local_private_directory_approval_ends_review_never_passed(self):
  r,suite,ticks,polls,rv,ev=dry(None,local=True);row=r['rows'][0]
  self.assertEqual((row['status'],row['result']),('FINISHED','REVIEW'));self.assertFalse(runner.gate(r['rows']));self.assertEqual(len(suite.uploaded),1);review.check_request(rv,ev,'777',10_001)
 def test_no_approval_never_ends_passed(self):
  r,suite,ticks,polls,rv,ev=dry(lambda *a:None,window=60)
  self.assertNotEqual(r['rows'][0]['result'],'PASSED');self.assertEqual(suite.uploaded,[])
 def test_approved_run_ends_review_never_passed_and_loop_stays_responsive(self):
  r,suite,ticks,polls,rv,ev=dry(ok);row=r['rows'][0]
  self.assertEqual((row['status'],row['result']),('FINISHED','REVIEW'));self.assertFalse(runner.gate(r['rows']));self.assertEqual(len(suite.uploaded),1);self.assertEqual(polls,3);self.assertGreater(ticks,5)
  review.check_request(rv,ev,'777',10_001)   # artifact gate accepts the exact pair
 def test_artifact_gate_rejects_tampering(self):
  r,suite,ticks,polls,rv,ev=dry(ok)
  png=rv/(MOD+'-verify-result.png');png.write_bytes(PNG+b'z')
  with self.assertRaises(review.ReviewError):review.check_request(rv,ev,'777',10_001)
  png.write_bytes(PNG);(rv/'extra.txt').write_text('x')
  with self.assertRaises(review.ReviewError):review.check_request(rv,ev,'777',10_001)
  (rv/'extra.txt').unlink()
  with self.assertRaises(review.ReviewError):review.check_request(rv,ev,'999',10_001)
  proj=ev/(MOD+'-verify-result.json');doc=json.loads(proj.read_text());doc['claims']='x';proj.write_text(json.dumps(doc))
  with self.assertRaises(review.ReviewError):review.check_request(rv,ev,'777',10_001)
 def test_no_approval_expires_without_upload_and_never_passes(self):
  r,suite,ticks,polls,rv,ev=dry(lambda m,n,now:None,window=60);row=r['rows'][0]
  self.assertEqual((row['status'],row['harness_category']),('HARNESS_ERROR','review_window_expired'));self.assertEqual(suite.uploaded,[])
 def test_wrong_hash_never_uploads(self):
  r,suite,*_=dry(lambda m,n,now:dict(ok(m,3,now),png_sha256='3'*64));self.assertEqual(r['rows'][0]['harness_category'],'approval_mismatch');self.assertEqual(suite.uploaded,[])
class Empty(unittest.TestCase):
 def test_empty_200_and_not_waiting_fail_closed(self):
  orig=Suite.respond
  def empty(self,req):
   if req.url.path.endswith('/images/ph_abcdef') and self.state=='WAITING':self.uploaded.append(b'x');return httpx.Response(200)
   return orig(self,req)
  Suite.respond=empty
  try:r,suite,*_=dry(ok);self.assertEqual(r['rows'][0]['harness_category'],'review_upload_failed')
  finally:Suite.respond=orig
  def finished(self,req):
   if req.url.path=='/api/info/'+MOD and self.uploaded==[] and getattr(self,'seen_review',False):self.state='FINISHED'
   if req.url.path.endswith('/api/log/'+MOD):self.seen_review=True
   return orig(self,req)
  Suite.respond=finished
  try:r,suite,*_=dry(ok);self.assertEqual(suite.uploaded,[])
  finally:Suite.respond=orig
if __name__=='__main__':unittest.main()
