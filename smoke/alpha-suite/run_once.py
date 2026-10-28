"""Prepared bounded official issuer run. Requires explicit run approval before launch."""
import datetime,json,os,pathlib,shutil,signal,subprocess,sys,time,uuid,requests
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'alpha-direct'));sys.path.insert(0,str(HERE.parent))
from prepare_runtime import prepare_suite
from tls_config import CERTIFY,AS,SUITE,NAMES
from official_driver import Driver
from safe_classic import json_object
from validate_readiness import health
from issue import seed
from gate import gate
OUT=ROOT/'alpha-suite-out';PROJECT='alpha-suite-isolated'
signal.signal(signal.SIGTERM,lambda signum,frame:(_ for _ in ()).throw(SystemExit(143)))

def main():
 run_id='alpha-suite-'+uuid.uuid4().hex;started=datetime.datetime.now(datetime.timezone.utc).isoformat();stage='prepare';private=None;compose=None;hosts=pathlib.Path('/etc/hosts');old_hosts=None;gate_exit=2
 try:
  private,compose=prepare_suite(OUT,os.environ['JAVA_HOME'])
  (OUT/'run-provenance.json').write_text(json.dumps({'id':run_id,'started_at':started,'requested':['issuer-metadata','issuer-happy-flow'],'identity':'synthetic TEST only','image':json.loads((HERE/'image-lock.json').read_text()),'actual_runtime':True},indent=2))
  cmd=['docker','compose','-p',PROJECT,'-f',str(compose)]
  def dc(*args,timeout=180):
   r=subprocess.run(cmd+list(args),capture_output=True,timeout=timeout)
   if r.returncode:raise RuntimeError('compose failure')
   return r.stdout
  stage='compose_validation';dc('config','--quiet',timeout=30)
  stage='hosts';old_hosts=hosts.read_text();addition='\n127.0.0.1 '+' '.join(NAMES)+'\n'
  subprocess.run(['sudo','tee','-a',str(hosts)],input=addition.encode(),capture_output=True,check=True)
  stage='startup';dc('up','-d',timeout=240)
  s=requests.Session();s.trust_env=False;s.verify=str(private/'tls-ca.pem')
  from readiness import wait
  for origin in ('certify','esignet','suite'):
   stage='readiness_'+origin
   wait(s,origin,OUT,cmd,cap=180)
  stage='stable_readiness_certify';time.sleep(15);wait(s,'certify',OUT,cmd,cap=30)
  stage='key_initialization'
  logs=dc('logs','--no-color','certify-app')
  if b'CERTIFY_PARTNER MASTER KEY CHECK' not in logs or b'Application run failed' in logs or b'Shutdown completed' in logs:raise ValueError('key initialization failure')
  del logs
  stage='configuration';base=CERTIFY+'/v1/certify/credential-configurations';dto=json.loads((ROOT/'smoke/alpha-init/mdl-credential-config.json').read_text())
  r=s.post(base,json=dto,timeout=20);b=json_object(r)
  if r.status_code!=201 or b.get('id')!='DrivingLicenseCredential':raise ValueError('configuration create failure')
  r=s.get(base+'/DrivingLicenseCredential',timeout=20);b=json_object(r)
  if b.get('credentialConfigKeyId')!='DrivingLicenseCredential':raise ValueError('configuration readback failure')
  md=json_object(s.get(CERTIFY+'/v1/certify/.well-known/openid-credential-issuer',timeout=20))
  if md.get('credential_issuer')!=CERTIFY or md.get('authorization_servers')!=[AS] or md.get('nonce_endpoint')!=CERTIFY+'/v1/certify/nonce':raise ValueError('metadata deployment mismatch')
  stage='synthetic_seed';seed()
  stage='official_modules';driver=Driver(private/'tls-ca.pem')
  try:driver.run(OUT,run_id,started)
  except Exception as de:
   (OUT/'suite-api-failure.json').write_text(json.dumps({'category':getattr(de,'category','driver_exception'),'error_class':type(de).__name__,'last_api':driver.last_api,'raw_values_retained':False}))
   raise
  stage='standalone_mosip_report';gate_exit=gate(OUT,run_id)
  stage='completed';(OUT/'completion.json').write_text(json.dumps({'official_modules_executed':True,'standalone_adapter_exit':gate_exit,'scope':'selected issuer modules, not full plan/certification','full_rig_s3_verified':False}))
 except Exception as e:
  OUT.mkdir(exist_ok=True)
  (OUT/'failure.json').write_text(json.dumps({'stage':stage,'error_class':type(e).__name__,'origin':getattr(e,'origin',None),'category':getattr(e,'category',None),'raw_body_retained':False}))
  if compose:
   try:
    from readiness import inspect
    from proxy_diagnostics import collect
    for diagnostic in (inspect,collect):
     try:diagnostic(cmd,OUT)
     except Exception as de:
      # A collector failure must not suppress other independent projections.
      print('DIAGNOSTIC_UNAVAILABLE '+type(de).__name__,flush=True)
    from safe_exception_causes import project
    r=subprocess.run(['docker','compose','-p',PROJECT,'-f',str(compose),'logs','--no-color'],capture_output=True,timeout=20)
    (OUT/'exception-causes.json').write_text(json.dumps(project(r.stdout.decode(errors='replace'))))
   except Exception:pass
  if (OUT/'conformance-results.json').exists() and stage!='standalone_mosip_report':
   try:gate(OUT,run_id)
   except Exception:pass
  print('::error::bounded alpha official run failed at '+stage+' ('+type(e).__name__+')')
  gate_exit=2
 finally:
  cleanup={'private_config_removed':False,'hosts_restored':False}
  if compose:
   r=subprocess.run(['docker','compose','-p',PROJECT,'-f',str(compose),'down','-v','--remove-orphans'],capture_output=True,timeout=120);cleanup['compose_down_exit']=r.returncode
   if r.returncode:gate_exit=2
  if old_hosts is not None:
   r=subprocess.run(['sudo','tee',str(hosts)],input=old_hosts.encode(),capture_output=True);cleanup['hosts_restored']=r.returncode==0 and hosts.read_text()==old_hosts
   if not cleanup['hosts_restored']:gate_exit=2
  if private:shutil.rmtree(private);cleanup['private_config_removed']=not private.exists()
  for kind in ('container','volume','network'):
   r=subprocess.run(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project='+PROJECT],capture_output=True,timeout=15);cleanup[kind+'_remaining']=len(r.stdout.splitlines()) if r.returncode==0 else 'unverified'
   if r.returncode or r.stdout.strip():gate_exit=2
  OUT.mkdir(exist_ok=True);(OUT/'cleanup.json').write_text(json.dumps(cleanup,indent=2))
 return gate_exit
if __name__=='__main__':sys.exit(main())
