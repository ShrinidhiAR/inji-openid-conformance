"""Strict readiness by actual harmless request validation, no record created."""
import time,requests
from contract import SERVICE,require

def wait(ca,timeout=180):
 s=requests.Session();s.verify=str(ca);s.trust_env=False;deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  try:
   # Invalid empty request must fail validation, not touch DB/create transaction.
   r=s.post(SERVICE+'/v2/vp-request',json={},timeout=5,allow_redirects=False)
   if r.status_code==400:
    require(r.headers.get('content-type','').split(';')[0]=='application/json','readiness_content_type')
    return {'https_request_validation_status':400,'readiness':'service route reachable; creation/result acceptance checked separately','schema_preflight':'separate compose verify-schema must exit0'}
  except requests.RequestException:pass
  time.sleep(3)
 raise ValueError('verify_readiness_timeout')
