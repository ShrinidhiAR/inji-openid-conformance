import asyncio,hashlib,json,pathlib,tempfile,unittest,httpx
import review,adapter,contract
PNG=b'\x89PNG\r\n\x1a\n'+b'x'*100
def manifest(now=1000,window=300):return review.make_manifest('12345','module12345678','ph_abcdef',PNG,window,now)
def approval(m,**kw):
 a={'schema':1,'run_id':m['run_id'],'test_id':m['test_id'],'png_sha256':m['png_sha256'],'approved_at':m['created_at']+5,'decision':'approve_faithful_view'};a.update(kw);return a
class Valid(unittest.TestCase):
 def check(self,a,now=1100,png=PNG,m=None):review.validate(a,m or manifest(),png,now)
 def rejects(self,category,a,**kw):
  with self.assertRaisesRegex(review.ReviewError,'^'+category+'$'):self.check(a,**kw)
 def test_valid(self):m=manifest();self.check(approval(m))
 def test_wrong_run_test_hash_decision_extra_keys(self):
  m=manifest()
  self.rejects('approval_mismatch',approval(m,run_id='99999'));self.rejects('approval_mismatch',approval(m,test_id='other1234567'));self.rejects('approval_mismatch',approval(m,png_sha256='0'*64))
  self.rejects('approval_invalid',approval(m,decision='approve'));self.rejects('approval_invalid',dict(approval(m),extra=1));self.rejects('approval_invalid',[])
 def test_image_changed_after_approval(self):
  m=manifest();self.rejects('approval_mismatch',approval(m),png=PNG+b'y')
 def test_stale_future_expired(self):
  m=manifest();self.rejects('approval_stale',approval(m,approved_at=m['created_at']-1));self.rejects('approval_invalid',approval(m,approved_at=5000),now=1100);self.rejects('review_window_expired',approval(m),now=m['deadline']+1)
 def test_bad_manifest_inputs(self):
  for args in (('bad id',"module12345678",'ph_abcdef',PNG,300,1),('1','module12345678','ph_abcdef',b'notpng',300,1),('1','module12345678','../x',PNG,300,1),('1','module12345678','ph_abcdef',PNG,601,1),('1','module12345678','ph_abcdef',PNG+b'0'*500000,300,1)):
   with self.assertRaises(review.ReviewError):review.make_manifest(*args)
class Wait(unittest.TestCase):
 def test_polls_then_accepts(self):
  m=manifest();clock=[1000];calls=[]
  async def source(path):
   calls.append(path);return None if len(calls)<3 else approval(m)
  async def sleep(s):clock[0]+=s
  asyncio.run(review.wait_for_approval(source,m,PNG,lambda:clock[0],sleep,15));self.assertEqual(len(calls),3);self.assertEqual(calls[0],'review-approvals/12345-module12345678.json')
 def test_timeout_and_mismatch_fail_closed(self):
  m=manifest(window=30);clock=[1000]
  async def none(p):return None
  async def sleep(s):clock[0]+=s
  with self.assertRaisesRegex(review.ReviewError,'review_window_expired'):asyncio.run(review.wait_for_approval(none,m,PNG,lambda:clock[0],sleep,15))
  async def bad(p):return approval(m,png_sha256='1'*64)
  with self.assertRaisesRegex(review.ReviewError,'approval_mismatch'):asyncio.run(review.wait_for_approval(bad,m,PNG,lambda:1000,sleep,15))
class Github(unittest.TestCase):
 env={'GITHUB_REPOSITORY':'o/r','GITHUB_TOKEN':'t0k','GITHUB_REF_NAME':'e2e-full-run'}
 def test_only_existing_branch_and_fixed_path(self):
  for bad in ({**env,'GITHUB_REF_NAME':'main'} for env in (self.env,)):
   with self.assertRaisesRegex(review.ReviewError,'review_configuration'):review.github_source(bad)
  seen=[]
  def respond(req):seen.append(req);return httpx.Response(404)
  src=review.github_source(self.env,httpx.AsyncClient(transport=httpx.MockTransport(respond)))
  self.assertIsNone(asyncio.run(src('review-approvals/12345-module12345678.json')));self.assertEqual(seen[0].method,'GET');self.assertEqual(dict(seen[0].url.params)['ref'],'e2e-full-run')
  with self.assertRaisesRegex(review.ReviewError,'review_configuration'):asyncio.run(src('../../etc/x'))
  r=httpx.AsyncClient(transport=httpx.MockTransport(lambda q:httpx.Response(500)));s2=review.github_source(self.env,r)
  with self.assertRaisesRegex(review.ReviewError,'approval_transport'):asyncio.run(s2('review-approvals/1-module12345678.json'))
class Flow(unittest.TestCase):
 def run_flow(self,approval_for,uploads,marks=('ph_abcdef',)):
  async def execute():
   tx={};clock=[1000]
   def respond(req):
    p=req.url.path
    if p.startswith('/api/runner/'):return httpx.Response(200,json={'id':'module12345678','name':'oid4vp-1final-verifier-happy-flow','browser':{'uriInputRequests':[{'submitUrl':'https://suite:8443/test/module12345678/authorize'}]}})
    if p.endswith('/v2/vp-request'):
     tx['id']=json.loads(req.content)['transactionId'];return httpx.Response(201,json={'transactionId':tx['id'],'requestId':'req_12345678-abcd-1234-abcd-123456789012','authorizationDetails':{'clientId':contract.CLIENT,'responseUri':contract.RESPONSE,'responseMode':'direct_post','responseType':'vp_token','dcqlQuery':contract.DCQL,'nonce':'n'*20,'responseCodeValidationRequired':False}})
    if p.endswith('/authorize'):return httpx.Response(200,text='ok')
    if '/v2/vp-results/' in p:return httpx.Response(200,json={'transactionId':tx['id'],'allChecksSuccessful':True,'credentialResults':[{'allChecksSuccessful':True,'schemaAndSignatureCheck':{'valid':True},'expiryCheck':{'valid':True},'holderProofCheck':{'valid':True},'statusCheck':[]}]})
    if p=='/api/info/module12345678':return httpx.Response(200,json={'testId':'module12345678','status':'WAITING'})
    if p=='/api/log/module12345678' and req.method=='GET':return httpx.Response(200,json=[{'msg':'x'}]+([{'upload':m} for m in marks] if not uploads else []))
    if p.startswith('/api/log/module12345678/images/'):uploads.append((p,req.content.decode()));return httpx.Response(200,json={'img':req.content.decode()})
    return httpx.Response(500)
   with tempfile.TemporaryDirectory() as tmp:
    rv=pathlib.Path(tmp)/'review'
    async def source(path):return approval_for(json.loads((rv/'manifest.json').read_text()),clock)
    async def sleep(s):clock[0]+=s
    cfg={'dir':rv,'window':300,'run_id':'12345','source':source,'clock':lambda:clock[0],'sleep':sleep,'interval':15}
    b=adapter.Adapter(True,tmp,review=cfg);await b.http.aclose();b.http=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    async def capture(html,module):(pathlib.Path(tmp)/(module+'-verify-result.png')).write_bytes(PNG)
    b.capture=capture
    try:
     await b('verify','module12345678',None);await b('verify','module12345678',None);return sorted(x.name for x in rv.iterdir())
    finally:await b.close()
  return asyncio.run(execute())
 def test_upload_only_after_matching_approval(self):
  up=[];files=self.run_flow(lambda m,c:approval(m),up)
  self.assertEqual(files,['manifest.json','module12345678-verify-result.png']);self.assertEqual(up,[('/api/log/module12345678/images/ph_abcdef',review.data_uri(PNG))])
 def test_mismatch_never_uploads(self):
  up=[]
  with self.assertRaisesRegex(contract.ContractError,'approval_mismatch'):self.run_flow(lambda m,c:approval(m,png_sha256='2'*64),up)
  self.assertEqual(up,[])
 def test_no_approval_expires_without_upload(self):
  up=[]
  with self.assertRaisesRegex(contract.ContractError,'review_window_expired'):self.run_flow(lambda m,c:None,up)
  self.assertEqual(up,[])
 def test_missing_or_ambiguous_placeholder_fails_closed(self):
  for marks in ((),('ph_abcdef','ph_ghijkl')):
   up=[]
   with self.assertRaisesRegex(contract.ContractError,'review_placeholder_missing'):self.run_flow(lambda m,c:approval(m),up,marks)
   self.assertEqual(up,[])
 def test_disabled_review_keeps_gate(self):
  # existing test_adapter covers the awaiting-review stop when review is None
  self.assertIsNone(adapter.Adapter(True,'/tmp').review)
if __name__=='__main__':unittest.main()
