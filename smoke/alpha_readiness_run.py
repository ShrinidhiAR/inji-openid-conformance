import datetime
from safe_exception_causes import project
import json,time,urllib.request,urllib.error,subprocess,pathlib,sys
from safe_http_evidence import summarize,Recorder
from validate_readiness import body,health,metadata,nonce,BASE,CONFIG
OUT=pathlib.Path('smoke-out');OUT.mkdir(exist_ok=True)
EVIDENCE=Recorder(OUT/'http-evidence.jsonl')
def request(path,method='GET',data=None):
    b=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(BASE+path,data=b,method=method,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as r: code,h,raw=r.status,dict(r.headers),r.read()
    except urllib.error.HTTPError as r: code,h,raw=r.code,dict(r.headers),r.read()
    except (urllib.error.URLError,TimeoutError,OSError) as e:
        EVIDENCE.record({'route':path,'http':None,'transport_error':type(e).__name__})
        raise ValueError('transport unavailable: '+type(e).__name__) from None
    EVIDENCE.record(summarize(path,code,h,raw))
    try:m=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError(f'{path}: non-JSON HTTP {code}')
    return code,h,m

def main():
    last='no response'
    # Bounded 120s; emit each changed response class immediately.
    for i in range(24):
        for p in ['/v1/certify/actuator/health','/actuator/health']:
            try:
                window=datetime.datetime.now(datetime.timezone.utc).isoformat()
                c,h,m=request(p)
                if p=='/v1/certify/actuator/health' and isinstance(m,dict) and m.get('errors'):
                    time.sleep(1)
                    rawlogs=subprocess.check_output(['docker','compose','-f','smoke/alpha-init/compose.yaml','logs','--no-color','--since',window,'certify-app'],text=True)
                    causes=project(rawlogs)
                    # This isolated request window has no config/issuance probes.
                    # Window association is evidence, not a cross-thread request ID.
                    (OUT/'health-request-causes.json').write_text(json.dumps({'scope':'isolated primary health request window','route':p,'http':c,'correlation':'container log timestamps since immediately before health GET; no other application probes','causes':causes},indent=2))
                    if causes:
                        print('HEALTH_REQUEST_EXCEPTION_CLASSES '+json.dumps([x['exception_classes'] for x in causes]),flush=True)
                        raise RuntimeError('captured primary health error with window-correlated exception; stopped early')
                health(c,m);healthpath=p;break
            except RuntimeError: raise
            except Exception as e:last=type(e).__name__+': '+str(e)
        else:time.sleep(5);continue
        break
    else:raise ValueError('health timeout: '+last)
    # Actuator UP must survive the ApplicationRunner, not just transient startup.
    time.sleep(15)
    c,h,m=request(healthpath);health(c,m)
    logs=subprocess.check_output(['docker','compose','-f','smoke/alpha-init/compose.yaml','logs','--no-color','certify-app'],text=True)
    if 'CERTIFY_PARTNER MASTER KEY CHECK' not in logs or 'Application run failed' in logs or 'Shutdown completed' in logs:raise ValueError('startup key initialization incomplete/failed')
    dto=json.loads(pathlib.Path('smoke/alpha-init/mdl-credential-config.json').read_text())
    c,h,m=request('/v1/certify/credential-configurations','POST',dto);body(c,m,201)
    if m.get('id')!=CONFIG or m.get('status')!='active':raise ValueError('config creation response mismatch')
    c,h,m=request('/v1/certify/credential-configurations/'+CONFIG);body(c,m)
    if m.get('credentialConfigKeyId')!=CONFIG or m.get('credentialFormat')!='mso_mdoc':raise ValueError('read-back mismatch')
    (OUT/'config-readback.json').write_text(json.dumps(m,indent=2))
    c,h,m=request('/v1/certify/.well-known/openid-credential-issuer');metadata(c,m)
    (OUT/'metadata.json').write_text(json.dumps(m,indent=2))
    endpoint=m['nonce_endpoint'].removeprefix(BASE)
    c,h,n=request(endpoint,'POST');nonce(c,n,h)
    # Never retain the nonce itself. Protocol status, not bearer material.
    result={'health':'UP after 15s stability check','key_initialization':'partner check reached; no fatal/shutdown','config':'created/read back','metadata':'Final fields validated','nonce':{'http':c,'c_nonce_present':True,'cache_control':h.get('Cache-Control')},'dpop_advertisement':m.get('dpop_signing_alg_values_supported','ABSENT'),'dpop_runtime_tested':False,'identity_payload':'mock/synthetic','credential_issuance_tested':False}
    (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':
    try:main()
    except Exception as e:
        # Errors include only HTTP/path/validator summaries, never server body or keys.
        print('::error::'+type(e).__name__+': '+str(e));sys.exit(1)
