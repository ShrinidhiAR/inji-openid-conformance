"""Two selected official modules, no body/secret logging, unchanged DPoP requests."""
import datetime,json,pathlib,re,sys,time,urllib.parse,uuid,requests
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'alpha-direct'))
from safe_classic import SafeClassic,json_object,ProtocolFailure
from esignet import gen_client_key
from tls_config import CERTIFY,AS,SUITE
from outcomes import document,write,safe_conditions
MODULES=['oid4vci-1_0-issuer-metadata-test','oid4vci-1_0-issuer-happy-flow']
VARIANT={'fapi_profile':'vci','credential_format':'mdoc','authorization_request_type':'simple','client_auth_type':'private_key_jwt','fapi_request_method':'unsigned','sender_constrain':'dpop','vci_authorization_code_flow_variant':'wallet_initiated','vci_credential_encryption':'plain','vci_grant_type':'authorization_code'}
ALIAS='alpha-official';CALLBACK=SUITE+'/test/a/'+ALIAS+'/callback'
class Driver:
 def __init__(self,ca):
  self.s=requests.Session();self.s.verify=str(ca);self.s.trust_env=False
  self.es=SafeClassic(AS,AS);self.es.s.verify=str(ca);self.es.s.trust_env=False
 def api(self,method,path,**kw):
  r=self.s.request(method,SUITE+path,timeout=40,**kw)
  if r.status_code not in (200,201,204):raise ProtocolFailure('suite API status')
  return r
 def browser(self,url):
  u=urllib.parse.urlsplit(url)
  if (u.scheme,u.netloc)!=(urllib.parse.urlsplit(AS).scheme,urllib.parse.urlsplit(AS).netloc):raise ProtocolFailure('unexpected auth origin')
  q=dict(urllib.parse.parse_qsl(u.query))
  if set(q)!={'client_id','request_uri'}:raise ProtocolFailure('expected PAR URL')
  d=self.es.par_oauth_details(q['client_id'],q['request_uri'])
  if d.get('credentialScopes')!=['sample_vc_mdoc'] or 'openid' in (d.get('authorizeScopes') or []):raise ProtocolFailure('unexpected resolved scope')
  self.es.authenticate(d['transactionId'],'1774231323')
  claims=list(dict.fromkeys((d.get('essentialClaims') or [])+(d.get('voluntaryClaims') or [])))
  ac=self.es.auth_code(d['transactionId'],claims,d.get('authorizeScopes') or [])
  if ac.get('redirectUri')!=CALLBACK or not ac.get('code') or ac.get('state') is None:raise ProtocolFailure('unexpected auth response')
  callback=CALLBACK+'?'+urllib.parse.urlencode({'code':ac['code'],'state':ac['state']})
  r=self.s.get(callback,allow_redirects=False,timeout=30)
  match=re.search("xhr\\.open\\('POST',\\s*['\"]([^'\"]+)",r.text)
  if not match:raise ProtocolFailure('missing implicit replay')
  raw=match.group(1)
  try:target=json.loads('"'+raw+'"')
  except ValueError:target=raw.replace('\\/','/')
  u=urllib.parse.urlsplit(target);origin=urllib.parse.urlsplit(SUITE)
  if (u.scheme,u.netloc)!=(origin.scheme,origin.netloc) or not u.path.startswith('/test/a/'+ALIAS+'/implicit/'):raise ProtocolFailure('unexpected replay target')
  r=self.s.post(target,data='',headers={'Content-Type':'text/plain'},timeout=30)
  if not 200<=r.status_code<300:raise ProtocolFailure('implicit replay failed')
 def run(self,out,run_id,started):
  info=self.api('GET','/api/plan/info/oid4vci-1_0-issuer-test-plan').json()
  variants=info.get('variants',{})
  for key,value in VARIANT.items():
   if value not in variants.get(key,{}).get('variantValues',{}):raise ProtocolFailure('pinned plan variant missing')
  actual_senders=set(variants['sender_constrain']['variantValues'])
  if actual_senders!={'mtls','dpop'}:raise ProtocolFailure('sender variant drift')
  names=[x.get('testModule') for x in info.get('modules',[])]
  if not all(x in names for x in MODULES):raise ProtocolFailure('module drift')
  (out/'plan-verification.json').write_text(json.dumps({'plan':info.get('planName'),'certifiable':info.get('certifiable'),'sender_constraints':sorted(actual_senders),'selected':MODULES,'image_lock_verified':True},indent=2))
  clients=[]
  for i in (1,2):
   cid='alpha-suite-'+str(i)+'-'+uuid.uuid4().hex[:8];_,pub,priv=gen_client_key()
   r=self.es._unwrap(self.es.register_client(cid,[CALLBACK],pub),'register')
   if r.get('clientId')!=cid:raise ProtocolFailure('registration mismatch')
   clients.append({'client_id':cid,'jwks':{'keys':[priv]}})
  cfg={'alias':ALIAS,'description':'Bounded real alpha issuer checks, synthetic TEST only','vci':{'credential_issuer_url':CERTIFY,'authorization_server':AS,'credential_configuration_id':'DrivingLicenseCredential','credential_proof_type_hint':'jwt'},'credential':{'trust_anchor_pem':(out/'mdoc-test-iaca.pem').read_text()},'client':clients[0],'client2':clients[1]}
  plan=self.api('POST','/api/plan',params={'planName':'oid4vci-1_0-issuer-test-plan','variant':json.dumps(VARIANT)},json=cfg).json();pid=plan.get('id') or plan.get('planId')
  if not pid:raise ProtocolFailure('no plan ID')
  rows=[];conditions={}
  for name in MODULES:
   mid=self.api('POST','/api/runner',params={'test':name,'plan':pid}).json().get('id')
   if not mid:raise ProtocolFailure('no module ID')
   self.api('POST','/api/runner/'+mid)
   deadline=time.monotonic()+240;driven=set();status='HARNESS_TIMEOUT';result=None
   while time.monotonic()<deadline:
    w=self.api('GET','/api/runner/'+mid+'/wait-state',params={'states':'WAITING,FINISHED,INTERRUPTED','timeoutMs':'20000'}).json()
    state=w.get('state') or w.get('status')
    if state=='WAITING':
     b=self.api('GET','/api/runner/browser/'+mid).json()
     for url in b.get('urls',[]):
      if url not in driven:
       driven.add(url)
       try:self.browser(url)
       except Exception:
        status='HARNESS_ERROR';result=None;break
     if status=='HARNESS_ERROR':break
    current=self.api('GET','/api/info/'+mid).json()
    if current.get('status') in ('FINISHED','INTERRUPTED'):
     status=current['status'];result=current.get('result');break
   rows.append({'module':name,'test_id':mid,'status':status,'result':result})
   # Preserve actual partial outcomes before optional condition read or next module.
   write(out/'conformance-results.json',document(run_id,started,pid,rows,[r['module'] for r in rows]))
   raw=self.api('GET','/api/log/'+mid).json()
   if not isinstance(raw,list):raise ProtocolFailure('unexpected suite event list')
   # DB API may call source src; only class-name/verdict allowlist retained.
   conditions[name]=safe_conditions([{'source':x.get('src') or x.get('source'),'result':x.get('result')} for x in raw if isinstance(x,dict)])
   del raw
   print(json.dumps(rows[-1]))
  doc=document(run_id,started,pid,rows,MODULES);write(out/'conformance-results.json',doc)
  (out/'condition-verdicts.json').write_text(json.dumps(conditions,indent=2))
  return doc
