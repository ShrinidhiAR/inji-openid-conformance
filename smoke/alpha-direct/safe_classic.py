"""Safe transport overrides for the existing source-grounded classic request shapes.
No original logging/error path is called. No HTTP response body is printed.
"""
import sys,pathlib,requests
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'e2e/scripts'))
from esignet_classic import EsignetClassic,API,_now
from esignet import client_assertion,DEFAULT_KID
class ProtocolFailure(RuntimeError):pass

def json_object(r):
    if r.status_code not in (200,201):raise ProtocolFailure('unexpected HTTP status')
    try:b=r.json()
    except ValueError:raise ProtocolFailure('non-JSON response') from None
    if not isinstance(b,dict) or b.get('errors') or b.get('error'):raise ProtocolFailure('protocol error envelope')
    return b
class SafeClassic(EsignetClassic):
    def _post(self,path,request,headers=None):
        self._ensure_csrf()
        return self.s.post(self.base+API+path,json={'requestTime':_now(),'request':request},headers=headers or {},timeout=30)
    def _unwrap(self,r,what):
        b=json_object(r);v=b.get('response')
        if not isinstance(v,dict):raise ProtocolFailure('missing response object')
        return v
    def exchange_code(self,code,client_id,private_pem,redirect_uri,kid=DEFAULT_KID):
        self._ensure_csrf()
        r=self.s.post(self.base+API+'/oauth/token',data={'grant_type':'authorization_code','code':code,'redirect_uri':redirect_uri,'client_id':client_id,'client_assertion_type':'urn:ietf:params:oauth:client-assertion-type:jwt-bearer','client_assertion':client_assertion(private_pem,client_id,self.issuer,kid)},timeout=30)
        b=json_object(r)
        if b.get('token_type','').lower()!='bearer' or not isinstance(b.get('access_token'),str):raise ProtocolFailure('unexpected token response')
        return b
    def authorization_code_flow(self,client_id,redirect_uri,scope,individual_id='1774231323',password='Mosip@123'):
        import uuid
        state=uuid.uuid4().hex
        d=self.oauth_details(client_id,redirect_uri,scope,state,uuid.uuid4().hex);tid=d['transactionId']
        self.authenticate(tid,individual_id,password)
        claims=list(dict.fromkeys((d.get('essentialClaims') or [])+(d.get('voluntaryClaims') or [])))
        ac=self.auth_code(tid,claims,d.get('authorizeScopes') or [])
        if not isinstance(ac.get('code'),str):raise ProtocolFailure('missing code')
        if ac.get('state') not in (None,state):raise ProtocolFailure('state mismatch')
        return ac['code']
