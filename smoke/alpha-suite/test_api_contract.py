"""Actual pinned VariantService output plus DTO-derived fixtures, never live outcomes."""
import copy,datetime,json,pathlib,tempfile,unittest,urllib.parse
from suite_contract import *
from official_driver import Driver,SUITE,AS,ALIAS,CALLBACK
FIXTURE=json.loads((pathlib.Path(__file__).parent/'fixtures/pinned-plan-info.json').read_text())
class Response:
 def __init__(self,b,status=200,text=''):self.b=b;self.status_code=status;self.text=text
 def json(self):return self.b
class APIContract(unittest.TestCase):
 def test_actual_pinned_plan_shape(self):
  self.assertEqual(plan_info(FIXTURE)['planName'],PLAN)
  for b in ({'data':[]},[],dict(FIXTURE,planName='wrong'),dict(FIXTURE,modules=[])):
   with self.assertRaises(ContractError):plan_info(b)
 def test_dto_contracts(self):
  self.assertEqual(wait_state({'timeout':True}),None);self.assertEqual(wait_state({'state':'WAITING'}),'WAITING')
  for b in ({'state':'unknown'},{'timeout':False},{'status':'WAITING'},[]):
   with self.assertRaises(ContractError):wait_state(b)
  for result in RESULTS:
   test_info({'testId':'module123456789','testName':MODULES[0],'status':'FINISHED','result':result},'module123456789',MODULES[0])
 def test_captured_callback_rendering(self):
  # Rendering style checked against /tmp/s4art2/suite-callback-page.html; random id replaced.
  target=SUITE+'/test/a/'+ALIAS+'/implicit/'+'A'*20
  page="xhr.open('POST', "+json.dumps(target).replace('/','\\/')+", true);"
  self.assertEqual(implicit_target(page,SUITE,ALIAS),target)
  for page in ("<html>wrong</html>","xhr.open('POST', \"https://outside.invalid/test/a/"+ALIAS+"/implicit/"+'A'*20+"\", true)"):
   with self.assertRaises(ContractError):implicit_target(page,SUITE,ALIAS)
 def test_transport_requests_and_two_actual_rows(self):
  # Fake HTTP responses are DTO-derived. This does NOT count as official execution.
  d=Driver('/unused-ca');calls=[];pid='plan123456789';mid={MODULES[0]:'metadata1234567',MODULES[1]:'happy1234567890'}
  def request(method,url,**kw):
   path=urllib.parse.urlsplit(url).path;calls.append((method,path,kw))
   self.assertFalse(kw['allow_redirects']);self.assertEqual(d.s.headers['Content-Type'],'application/json')
   if path==PLAN_ROUTE:return Response(FIXTURE)
   if path=='/api/plan':
    self.assertEqual(json.loads(kw['params']['variant']),VARIANT);self.assertIn('client',kw['json'])
    return Response({'id':pid,'name':PLAN,'modules':FIXTURE['selectedVariantModules']},201)
   if path=='/api/runner':
    self.assertNotIn('json',kw);self.assertNotIn('data',kw);name=kw['params']['test'];return Response({'id':mid[name],'name':name,'url':SUITE+'/test/a/'+ALIAS},201)
   name=next(n for n,id in mid.items() if id in path);id=mid[name]
   if path.endswith('/wait-state'):return Response({'state':'FINISHED'})
   if path.startswith('/api/runner/'):return Response({'id':id,'name':name})
   if path.startswith('/api/info/'):return Response({'testId':id,'testName':name,'status':'FINISHED','result':'FAILED','config':{'secret':'do not copy'}})
   if path.startswith('/api/log/'):return Response([{'src':'CheckMetadata','result':'FAILURE','args':{'secret':'never copy'}}])
   self.fail('unexpected path')
  d.s.request=request
  d.es.register_client=lambda cid,*a:Response({'response':{'clientId':cid}})
  with tempfile.TemporaryDirectory() as p:
   out=pathlib.Path(p);(out/'mdoc-test-iaca.pem').write_text('fixture public cert')
   result=d.run(out,'fixture-run',datetime.datetime.now(datetime.timezone.utc).isoformat())
   self.assertEqual(len(result['certify']),2);self.assertEqual({r['result'] for r in result['certify']},{'FAILED'})
   self.assertNotIn('secret',(out/'condition-verdicts.json').read_text());self.assertNotIn('secret',(out/'conformance-results.json').read_text())
  self.assertEqual(len([c for c in calls if c[0]=='POST' and c[1]=='/api/runner']),2)
 def test_browser_flow_mirrors_pinned_ui_configured_issuer(self):
  d=Driver('/unused-ca');posted=[];d.es.par_oauth_details=lambda *a:{'transactionId':'fixture','credentialScopes':['sample_vc_mdoc'],'authorizeScopes':[],'configs':{'issuer':AS}}
  d.es.authenticate=lambda *a:{};d.es.auth_code=lambda *a:{'redirectUri':CALLBACK,'code':'fake +&','state':'fake &=','nonce':'not-forwarded'}
  target=SUITE+'/test/a/'+ALIAS+'/implicit/'+'A'*20
  def get(url,**kw):
   self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query),{'code':['fake +&'],'state':['fake &='],'iss':[AS]});return Response(None,200,"xhr.open('POST',"+json.dumps(target)+",true)")
  d.s.get=get;d.s.post=lambda url,**kw:(posted.append((url,kw)) or Response(None,204))
  with tempfile.TemporaryDirectory() as evidence_dir:
   d.es.out=pathlib.Path(evidence_dir)
   d.browser(AS+'/authorize?client_id=fixture&request_uri=fixture')
  self.assertEqual(posted[0][1]['data'],'');self.assertEqual(posted[0][1]['headers']['Content-Type'],'text/plain')
  with self.assertRaises(ContractError):d.browser(AS+'/authorize?client_id=fixture&client_id=duplicate&request_uri=fixture')
  for configs in ({},{'issuer':'https://wrong.invalid'}):
   d.es.par_oauth_details=lambda *a:{'transactionId':'fixture','credentialScopes':['sample_vc_mdoc'],'authorizeScopes':[],'configs':configs}
   with self.assertRaises(ContractError):d.browser(AS+'/authorize?client_id=fixture&request_uri=fixture')
if __name__=='__main__':unittest.main()
