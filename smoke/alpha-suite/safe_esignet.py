"""Exact existing SafeClassic requests with allowlisted response diagnostics only."""
import json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'alpha-direct'))
from safe_classic import SafeClassic,ProtocolFailure
ROUTES={'/client-mgmt/oauth-client','/authorization/par-oauth-details','/authorization/authenticate','/authorization/auth-code'}
CODES={'invalid_redirect_uri','invalid_client_id','invalid_rp_id','invalid_client_name','invalid_public_key','invalid_claim','invalid_acr','invalid_uri','unsupported_grant_type','invalid_client_auth','invalid_request','invalid_request_time','invalid_transaction','invalid_transaction_id','invalid_request_uri','invalid_identifier','invalid_challenge_list','invalid_accepted_claim','invalid_permitted_scope','invalid_auth_factor_type','invalid_challenge_format'}
FIELDS={'requestTime','request.clientId','request.relyingPartyId','request.clientName','request.publicKey','request.logoUri','request.clientNameLangMap','request.transactionId','request.requestUri','request.individualId','request.challengeList'}
for prefix in ('redirectUris','userClaims','authContextRefs','grantTypes','clientAuthMethods','acceptedClaims','permittedAuthorizeScopes'):
 FIELDS.add('request.'+prefix)
 for i in range(30):FIELDS.add('request.'+prefix+'['+str(i)+']')
def project(route,r):
 result={'route':route if route in ROUTES else '<other>','http':r.status_code}
 try:b=r.json()
 except ValueError:result['shape']='non-json';return result
 result['shape']='object' if isinstance(b,dict) else 'other';es=b.get('errors') if isinstance(b,dict) else None
 result['error_envelope']=bool(es);result['errors']=[]
 if isinstance(es,list):
  for e in es[:12]:
   if not isinstance(e,dict):continue
   code=e.get('errorCode');msg=e.get('errorMessage');field=msg.split(':',1)[0] if isinstance(msg,str) else None
   result['errors'].append({'code':code if code in CODES else '<other>','field':field if field in FIELDS else '<other>'})
 return result
class SafeEsignet(SafeClassic):
 def __init__(self,base,issuer,out):super().__init__(base,issuer);self.out=pathlib.Path(out)
 def _post(self,path,request,headers=None):
  r=super()._post(path,request,headers);e=project(path,r)
  with (self.out/'as-http-evidence.jsonl').open('a') as f:f.write(json.dumps(e)+'\n')
  print('AS_HTTP '+json.dumps(e),flush=True);return r
