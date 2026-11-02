"""Prepared single-run entry point. No automatic retry of issuance/auth flows.
Runtime private config is deleted after compose cleanup; stdout is allowlisted.
"""
import json,os,pathlib,shutil,signal,subprocess,sys,time,yaml,requests
from runtime_signer import prepare
from safe_classic import json_object
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'smoke'))
from validate_readiness import health,body,metadata
OUT=ROOT/'alpha-direct-out'
signal.signal(signal.SIGTERM,lambda signum,frame:(_ for _ in ()).throw(SystemExit(143)))

def bundle(private):
    # Merge complete alpha release DB initializer, never old certify mounts.
    files=[ROOT/'smoke/alpha-init/compose.yaml',ROOT/'e2e/compose/esignet/docker-compose.yaml']
    combined={'services':{},'networks':{'e2e-net':{}}}
    for file in files:
        m=yaml.safe_load(file.read_text())
        for name,svc in m['services'].items():
            svc.pop('container_name',None);svc['networks']=['e2e-net']
            vols=[]
            for v in svc.get('volumes',[]):
                parts=v.split(':');src=parts[0]
                if src.startswith('.'):
                    src=str((file.parent/src).resolve())
                parts[0]=src;vols.append(':'.join(parts))
            if vols:svc['volumes']=vols
            # All host debug ports are loopback-only for this isolated test.
            svc['ports']=[p if p.startswith('127.0.0.1:') else '127.0.0.1:'+p for p in svc.get('ports',[])]
            combined['services'][name]=svc
    combined['services']['certify-app']['volumes']=[str(private/'config')+':/home/mosip/config:ro']
    # Removing global redis container_name requires the source's redis hostname alias.
    combined['services']['redis']['networks']={'e2e-net':{'aliases':['redis-server']}}
    combined['services']['esignet-gateway']['networks']={'e2e-net':{'aliases':['esignet']}}
    p=private/'compose.yaml';p.write_text(yaml.safe_dump(combined));os.chmod(p,0o600)
    return p,combined

def wait_ready(url,deadline):
    while time.monotonic()<deadline:
        try:
            r=requests.get(url,timeout=5);m=json_object(r)
            if 'actuator/health' in url:health(r.status_code,m)
            elif not m.get('issuer'):raise ValueError('missing issuer')
            return
        except (requests.RequestException,ValueError,RuntimeError):time.sleep(5)
    raise TimeoutError('readiness deadline')

def main():
    if OUT.exists():raise RuntimeError('refuse previous evidence directory')
    OUT.mkdir();private,cert=prepare(ROOT/'smoke/alpha-init/config',OUT);stage='runtime_config';compose=None
    try:
        # Exact external authorization contract; do not activate alpha local profile.
        p=private/'config/certify-default.properties';s=p.read_text()
        replacements={'mosip.certify.authorization.url':'http://esignet:8088','mosip.certify.authn.issuer-uri':'http://esignet:8088','mosip.certify.authn.jwk-set-uri':'http://esignet:8088/v1/esignet/oauth/.well-known/jwks.json','mosip.certify.authn.allowed-audiences':"{ 'http://esignet:8088/v1/esignet/vci/credential' }"}
        lines=s.splitlines()
        for key,value in replacements.items():
            if sum(x.startswith(key+'=') for x in lines)!=1:raise ValueError('configuration key ambiguity')
            lines=[key+'='+value if x.startswith(key+'=') else x for x in lines]
        p.write_text('\n'.join(lines)+'\n');os.chmod(p,0o600)
        compose,model=bundle(private)
        cmd=['docker','compose','-p','alpha-direct-isolated','-f',str(compose)]
        def dc(*args,timeout=120):
            r=subprocess.run(cmd+list(args),capture_output=True,timeout=timeout)
            if r.returncode:raise RuntimeError('compose command failed')
            return r.stdout
        stage='compose_validation';dc('config','--quiet',timeout=30)
        stage='start';dc('up','-d',timeout=180)
        stage='readiness';deadline=time.monotonic()+600
        wait_ready('http://localhost:8099/v1/certify/actuator/health',deadline)
        wait_ready('http://localhost:8090/v1/esignet/oidc/.well-known/openid-configuration',deadline)
        wait_ready('http://localhost:8082/v1/mock-identity-system/actuator/health',deadline)
        time.sleep(15)
        r=requests.get('http://localhost:8099/v1/certify/actuator/health',timeout=10);health(r.status_code,json_object(r))
        logs=dc('logs','--no-color','certify-app')
        if b'CERTIFY_PARTNER MASTER KEY CHECK' not in logs or b'Application run failed' in logs or b'Shutdown completed' in logs:raise ValueError('key initialization failed')
        del logs
        stage='configuration'
        dto=json.loads((ROOT/'smoke/alpha-init/mdl-credential-config.json').read_text())
        base='http://localhost:8099/v1/certify/credential-configurations'
        r=requests.post(base,json=dto,timeout=20);b=json_object(r);body(r.status_code,b,201)
        if b.get('id')!='DrivingLicenseCredential' or b.get('status')!='active':raise ValueError('configuration creation mismatch')
        r=requests.get(base+'/DrivingLicenseCredential',timeout=20);b=json_object(r)
        if b.get('credentialConfigKeyId')!='DrivingLicenseCredential' or b.get('credentialFormat')!='mso_mdoc':raise ValueError('configuration readback mismatch')
        stage='one_issuance'
        from issue import main as issue
        issue(OUT)
        stage='completed'
    except Exception as e:
        (OUT/'failure.json').write_text(json.dumps({'stage':stage,'error_class':type(e).__name__,'raw_logs_retained':False}))
        if compose:
            try:
                from safe_exception_causes import project
                raw=subprocess.run(['docker','compose','-p','alpha-direct-isolated','-f',str(compose),'logs','--no-color'],capture_output=True,timeout=20)
                (OUT/'exception-causes.json').write_text(json.dumps(project(raw.stdout.decode(errors='replace'))))
                del raw
            except Exception:pass
        print('::error::alpha direct failed at '+stage+' ('+type(e).__name__+')');raise SystemExit(1) from None
    finally:
        try:
            if compose:
                r=subprocess.run(['docker','compose','-p','alpha-direct-isolated','-f',str(compose),'down','-v','--remove-orphans'],capture_output=True,timeout=120)
                if r.returncode:raise RuntimeError('cleanup failed')
                (OUT/'cleanup.json').write_text(json.dumps({'compose_down_exit':r.returncode,'private_config_removal':'finally block follows'}))
        finally:
            shutil.rmtree(private)
            cleanup=OUT/'cleanup.json'
            if cleanup.exists():
                b=json.loads(cleanup.read_text());b.pop('private_config_removal',None);b['private_config_removed']=not private.exists()
                for kind in ('container','volume','network'):
                    r=subprocess.run(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project=alpha-direct-isolated'],capture_output=True,timeout=15)
                    if r.returncode or r.stdout.strip():raise RuntimeError('cleanup verification failed')
                    b[kind+'_remaining']=0
                cleanup.write_text(json.dumps(b))
if __name__=='__main__':main()
