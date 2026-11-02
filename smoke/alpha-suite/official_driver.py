"""Two selected official modules, no body/secret logging, unchanged DPoP requests."""
import datetime,json,pathlib,re,sys,time,urllib.parse,uuid,requests
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'alpha-direct'))
from safe_classic import json_object,ProtocolFailure
from safe_esignet import SafeEsignet
from esignet import gen_client_key
from tls_config import CERTIFY,AS,SUITE
from outcomes import document,write,safe_conditions
from fetch_diagnostics import project as fetch_diagnostics
from stage_diagnostics import project as stage_diagnostics,browser as browser_diagnostics
from suite_contract import PLAN,PLAN_ROUTE,MODULES,VARIANT,plan_info,created_plan,created_module,wait_state,test_info,implicit_target,require,ContractError
ALIAS='alpha-official';CALLBACK=SUITE+'/test/a/'+ALIAS+'/callback'
class Driver:
 def __init__(self,ca,out=None):
  self.s=requests.Session();self.s.verify=str(ca);self.s.trust_env=False;self.s.headers.update({'Content-Type':'application/json'})
  self.last_api=None
  self.es=SafeEsignet(AS,AS,out or pathlib.Path.cwd());self.es.s.verify=str(ca);self.es.s.trust_env=False
 def api(self,method,path,expected=200,**kw):
  self.last_api={'method':method,'path_template':re.sub(r'/[A-Za-z0-9]{8,32}(?=/|$)','/<id>',path),'expected_http':expected}
  r=self.s.request(method,SUITE+path,timeout=40,allow_redirects=False,**kw)
  self.last_api['actual_http']=r.status_code
  print('SUITE_API '+json.dumps(self.last_api),flush=True)
  if r.status_code!=expected:raise ContractError('suite_api_http_'+str(r.status_code))
  return r
 def browser(self,url):
  u=urllib.parse.urlsplit(url)
  if (u.scheme,u.netloc)!=(urllib.parse.urlsplit(AS).scheme,urllib.parse.urlsplit(AS).netloc):raise ProtocolFailure('unexpected auth origin')
  pairs=urllib.parse.parse_qsl(u.query,keep_blank_values=True);q=dict(pairs)
  require(len(pairs)==len(q) and not u.fragment and u.path=='/authorize','authorize_url_contract')
  if set(q)!={'client_id','request_uri'} or not all(q.values()):raise ProtocolFailure('expected PAR URL')
  d=self.es.par_oauth_details(q['client_id'],q['request_uri'])
  if d.get('credentialScopes')!=['sample_vc_mdoc'] or 'openid' in (d.get('authorizeScopes') or []):raise ProtocolFailure('unexpected resolved scope')
  self.es.authenticate(d['transactionId'],'1774231323')
  claims=list(dict.fromkeys((d.get('essentialClaims') or [])+(d.get('voluntaryClaims') or [])))
  ac=self.es.auth_code(d['transactionId'],claims,d.get('authorizeScopes') or [])
  if ac.get('redirectUri')!=CALLBACK or not ac.get('code') or ac.get('state') is None:raise ProtocolFailure('unexpected auth response')
  # Pinned eSignet UI Consent.js/ClaimDetails.js takes iss from oauth details configs.
  configs=d.get('configs')
  require(isinstance(configs,dict) and configs.get('issuer')==AS,'ui_configured_issuer_contract')
  callback_query={'code':ac['code'],'state':ac['state'],'iss':configs['issuer']}
  with (self.es.out/'browser-evidence.jsonl').open('a') as fh:fh.write(json.dumps(browser_diagnostics(d,callback_query,AS))+'\n')
  callback=CALLBACK+'?'+urllib.parse.urlencode(callback_query)
  r=self.s.get(callback,allow_redirects=False,timeout=30)
  require(r.status_code==200,'callback_status_contract')
  target=implicit_target(r.text,SUITE,ALIAS)
  r=self.s.post(target,data='',headers={'Content-Type':'text/plain'},timeout=30,allow_redirects=False)
  require(r.status_code==204,'implicit_submit_status_contract')

 def configuration(self,out):
  clients=[]
  for i in (1,2):
   cid='alpha-suite-'+str(i)+'-'+uuid.uuid4().hex[:8];_,pub,priv=gen_client_key()
   r=self.es._unwrap(self.es.register_client(cid,[CALLBACK],pub),'register')
   if r.get('clientId')!=cid:raise ProtocolFailure('registration mismatch')
   clients.append({'client_id':cid,'jwks':{'keys':[priv]}})
  cfg={'alias':ALIAS,'description':'Bounded real alpha issuer checks, synthetic TEST only','vci':{'credential_issuer_url':CERTIFY,'authorization_server':AS,'credential_configuration_id':'DrivingLicenseCredential','credential_proof_type_hint':'jwt'},'credential':{'trust_anchor_pem':(out/'mdoc-test-iaca.pem').read_text()},'client':clients[0],'client2':clients[1]}
  return cfg

 def run(self,out,run_id,started):
  info=plan_info(self.api('GET',PLAN_ROUTE).json())
  actual_senders=set(info['variants']['sender_constrain']['variantValues'])
  (out/'plan-verification.json').write_text(json.dumps({'plan':info.get('planName'),'certifiable':info.get('certifiable'),'sender_constraints':sorted(actual_senders),'selected':MODULES,'image_lock_verified':True},indent=2))
  cfg=self.configuration(out)
  plan=self.api('POST','/api/plan',expected=201,params={'planName':PLAN,'variant':json.dumps(VARIANT)},json=cfg).json();pid=created_plan(plan)
  if not pid:raise ProtocolFailure('no plan ID')
  rows=[];conditions={}
  for name in MODULES:
   mid=created_module(self.api('POST','/api/runner',expected=201,params={'test':name,'plan':pid}).json(),name)
   if not mid:raise ProtocolFailure('no module ID')
   start=self.api('POST','/api/runner/'+mid).json()
   require(start.get('id')==mid and start.get('name')==name,'start_test_contract')
   deadline=time.monotonic()+240;driven=set();status='HARNESS_TIMEOUT';result=None
   while time.monotonic()<deadline:
    w=self.api('GET','/api/runner/'+mid+'/wait-state',params={'states':'WAITING,FINISHED,INTERRUPTED','timeoutMs':'20000'}).json()
    state=wait_state(w)
    if state=='WAITING':
     b=self.api('GET','/api/runner/browser/'+mid).json()
     require(b.get('id')==mid and isinstance(b.get('urls'),list) and all(isinstance(u,str) for u in b['urls']),'browser_status_contract')
     for url in b['urls']:
      if url not in driven:
       driven.add(url)
       try:self.browser(url)
       except Exception as be:
        (out/'suite-api-failure.json').write_text(json.dumps({'category':getattr(be,'category','browser_driver_exception'),'error_class':type(be).__name__,'last_api':self.last_api,'raw_values_retained':False}))
        status='HARNESS_ERROR';result=None;break
     if status=='HARNESS_ERROR':break
    current=test_info(self.api('GET','/api/info/'+mid).json(),mid,name)
    if current.get('status')=='WAITING':time.sleep(0.5)
    if current.get('status') in ('FINISHED','INTERRUPTED'):
     status=current['status'];result=current.get('result');break
   rows.append({'module':name,'test_id':mid,'status':status,'result':result})
   # Preserve actual partial outcomes before optional condition read or next module.
   write(out/'conformance-results.json',document(run_id,started,pid,rows,[r['module'] for r in rows]))
   raw=self.api('GET','/api/log/'+mid).json()
   if not isinstance(raw,list):raise ProtocolFailure('unexpected suite event list')
   # DB API may call source src; only class-name/verdict allowlist retained.
   with (out/'metadata-fetch-evidence.jsonl').open('a') as fh:
    fh.write(json.dumps({'module':name,'fetch':fetch_diagnostics(raw)})+'\n')
   conditions[name]=safe_conditions([{'source':x.get('src') or x.get('source'),'result':x.get('result')} for x in raw if isinstance(x,dict)])
   with (out/'stage-diagnostics.jsonl').open('a') as fh:
    fh.write(json.dumps({'module':name,'events':stage_diagnostics(raw)})+'\n')
   del raw
   print(json.dumps(rows[-1]))
  doc=document(run_id,started,pid,rows,MODULES);write(out/'conformance-results.json',doc)
  (out/'condition-verdicts.json').write_text(json.dumps(conditions,indent=2))
  return doc
