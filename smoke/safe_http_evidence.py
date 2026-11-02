"""Allowlisted HTTP evidence only. Never include response bodies or error text."""
import json,re
STATUSES={'UP','DOWN','OUT_OF_SERVICE','UNKNOWN'}
CODES={'unknown_error','invalid_token','invalid_request','access_denied','unauthorized','forbidden','invalid_client','not_found'}
COMPONENTS={'db','diskSpace','ping','redis','refreshScope','discoveryComposite','clientConfigServer','keymanager','keyManager','hsm'}
def summarize(route,code,headers,raw):
    # Caller paths are controlled, never copy URLs returned by a server.
    if route not in {'/actuator/health','/v1/certify/actuator/health','/v1/certify/credential-configurations','/v1/certify/credential-configurations/DrivingLicenseCredential','/v1/certify/.well-known/openid-credential-issuer','/v1/certify/nonce'}:route='<other-local-route>'
    h={k.lower():v for k,v in headers.items()}
    ct=h.get('content-type','').split(';')[0].strip().lower()
    ct=ct if ct in {'application/json','application/vnd.spring-boot.actuator.v3+json','application/vnd.spring-boot.actuator.v2+json','text/html','text/plain'} else '<other-or-missing>'
    out={'route':route,'http':code,'content_type':ct}
    try:m=json.loads(raw)
    except (ValueError,UnicodeDecodeError):out['shape']='non-json';return out
    if not isinstance(m,dict):out['shape']='non-object';return out
    out['shape']='object'
    if 'status' in m:out['health_status']=m['status'] if isinstance(m['status'],str) and m['status'] in STATUSES else '<unrecognized>'
    if 'errors' in m:
        es=m['errors'];out['error_envelope']=bool(es)
        out['error_codes']=[e.get('errorCode') if e.get('errorCode') in CODES else '<other>' for e in es[:8] if isinstance(e,dict)] if isinstance(es,list) else ['<invalid-errors-shape>']
    if isinstance(m.get('components'),dict):
        out['components']={k:(v.get('status') if isinstance(v,dict) and isinstance(v.get('status'),str) and v['status'] in STATUSES else '<unrecognized>') for k,v in m['components'].items() if k in COMPONENTS}
    if 'status' not in m and 'errors' not in m:out['shape']='object-without-health-or-error-fields'
    return out
class Recorder:
    def __init__(self,path):self.path=path;self.last={}
    def record(self,evidence):
        route=evidence['route'];sig=json.dumps(evidence,sort_keys=True)
        if self.last.get(route)==sig:return
        self.last[route]=sig
        with self.path.open('a') as fh:fh.write(sig+'\n')
        print('HTTP_EVIDENCE '+sig,flush=True)
