"""Changed-class evidence for controlled local origins. Never messages/bodies/logs."""
import json,pathlib,socket,ssl,time,subprocess,requests,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from safe_http_evidence import summarize,Recorder
from suite_contract import PLAN_ROUTE,plan_info,ContractError
ORIGINS={'certify':('/v1/certify/actuator/health','certify.local.test'),'esignet':('/v1/esignet/oidc/.well-known/openid-configuration','esignet.local.test'),'suite':(PLAN_ROUTE,'suite.local.test')}
SERVICES={'certify-app','initialize','certify-db','esignet-app','esignet-db','redis','mock-identity-system','mock-ready','esignet-gateway','suite-server','suite-mongodb','tls-gateway'}
CATS={10:'certificate_expired',18:'self_signed_leaf',19:'self_signed_chain',20:'issuer_unavailable',21:'leaf_signature_unverified',62:'hostname_mismatch',85:'authority_key_identifier_missing',86:'subject_key_identifier_missing'}

def exception(e):
    seen=set();todo=[e];classes=[];verify=None
    while todo:
        x=todo.pop()
        if id(x) in seen:continue
        seen.add(id(x))
        name=type(x).__name__
        if name in {'SSLError','SSLCertVerificationError','MaxRetryError','NewConnectionError','ConnectionError','ConnectTimeout','ReadTimeout','TimeoutError','gaierror','ConnectionRefusedError','ProtocolError'}:classes.append(name)
        if isinstance(x,ssl.SSLCertVerificationError):verify=x.verify_code
        for a in ('__cause__','__context__','reason'):
            v=getattr(x,a,None)
            if isinstance(v,BaseException):todo.append(v)
        todo.extend(a for a in getattr(x,'args',()) if isinstance(a,BaseException))
    category='transport_error'
    if verify is not None:category=CATS.get(verify,'certificate_verification_other')
    elif any(x in classes for x in ('ConnectTimeout','ReadTimeout','TimeoutError')):category='timeout'
    elif 'gaierror' in classes:category='dns_error'
    elif 'ConnectionRefusedError' in classes or 'NewConnectionError' in classes:category='connection_unavailable'
    elif 'SSLError' in classes:category='tls_handshake_error'
    return {'category':category,'exception_classes':sorted(set(classes)),'tls_verify_code':verify}

def lifecycle(model):
    # Input already selected from docker inspect's State and service label only.
    out=[]
    for m in model:
        service=m.get('service');state=m.get('state',{})
        if service not in SERVICES:continue
        status=state.get('Status');h=state.get('Health',{}).get('Status')
        out.append({'service':service,'status':status if status in {'created','running','paused','restarting','removing','exited','dead'} else 'other','exit_code':state.get('ExitCode') if isinstance(state.get('ExitCode'),int) else None,'oom_killed':state.get('OOMKilled') is True,'health':h if h in {'starting','healthy','unhealthy'} else None})
    return out

def inspect(cmd,out):
    ids=subprocess.run(cmd+['ps','-aq'],capture_output=True,text=True,timeout=10)
    rows=[]
    if ids.returncode:raise ReadinessFailure('lifecycle','inspect_unavailable')
    for id in ids.stdout.splitlines():
        r=subprocess.run(['docker','inspect','--format','{{json .State}}',id],capture_output=True,text=True,timeout=10)
        n=subprocess.run(['docker','inspect','--format','{{index .Config.Labels "com.docker.compose.service"}}',id],capture_output=True,text=True,timeout=10)
        if r.returncode==n.returncode==0:
            try:rows.append({'service':n.stdout.strip(),'state':json.loads(r.stdout)})
            except ValueError:raise ReadinessFailure('lifecycle','inspect_invalid_json')
        else:raise ReadinessFailure('lifecycle','container_inspect_unavailable')
    safe=lifecycle(rows);(out/'lifecycle.json').write_text(json.dumps(safe,indent=2));return safe

def terminal(rows):
    return any(r['status'] in {'dead','restarting'} or r['oom_killed'] or r['status']=='exited' and (r['service'] not in {'initialize','mock-ready'} or r['exit_code']!=0) for r in rows)

class ReadinessFailure(RuntimeError):
    def __init__(self,origin,category):self.origin=origin;self.category=category;super().__init__(origin+':'+category)

def wait(session,origin,out,cmd,cap=180,clock=time.monotonic,sleep=time.sleep,inspect_fn=inspect):
    route,host=ORIGINS[origin];rec=Recorder(out/'readiness.jsonl');deadline=clock()+cap;last='no_response';last_life=None
    def record(e):
        e.update({'origin':origin,'route':route,'record_key':origin+route});rec.record(e)
    while clock()<deadline:
        rows=inspect_fn(cmd,out)
        sig=json.dumps(rows,sort_keys=True)
        if sig!=last_life:
            print('LIFECYCLE '+sig,flush=True);last_life=sig
        if terminal(rows):
            record({'category':'terminal_process_state'});raise ReadinessFailure(origin,'terminal_process_state')
        try:
            r=session.get('https://'+host+':8443'+route,timeout=max(0.1,min(6,deadline-clock())))
            e=summarize(route,r.status_code,r.headers,r.content);e['category']='http_response'
            try:b=r.json()
            except ValueError:b=None
            if origin=='suite':
                try:plan_info(b);e['plan_contract_matches']=True
                except ContractError:e['plan_contract_matches']=False
            if origin=='esignet':e['issuer_matches']=isinstance(b,dict) and b.get('issuer')=='https://'+host+':8443'
            record(e);last='http_'+str(r.status_code)
            if origin=='suite' and r.status_code==200 and not e['plan_contract_matches']:raise ReadinessFailure(origin,'plan_contract_mismatch')
            ok=r.status_code==200 and ((origin=='certify' and isinstance(b,dict) and b.get('status')=='UP' and not b.get('errors')) or (origin=='esignet' and e['issuer_matches']) or (origin=='suite' and e['plan_contract_matches']))
            if ok:return
        except requests.RequestException as ex:
            e=exception(ex);record(e);last=e['category']
            if e['tls_verify_code'] is not None:raise ReadinessFailure(origin,last) from None
        sleep(max(0,min(5,deadline-clock())))
    record({'category':'deadline','last_category':last});raise ReadinessFailure(origin,'deadline_'+last)
