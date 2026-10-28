"""One owned synthetic stack, both native rigs, truthful combined gate.

Prepared only. Requires explicit runtime approval, pinned MinIOimage and already
compiled exact nativecomponents. No push/merge/paid resources. CAverified clients.
"""
import pathlib,sys,os,json,uuid,subprocess,shutil,datetime,signal
ROOT=pathlib.Path(__file__).resolve().parents[1]
from prepare_combined import prepare
from run_native import invoke
from owned_process import run as owned_run
from cleanup import cleanup

def main(args):
 review_token=os.environ.pop('GITHUB_TOKEN',None) if os.environ.get('CONFORMANCE_REVIEW_WINDOW') else None  # never inherited by compose, certify or MinIO
 out=pathlib.Path(args.output).resolve();private=None;compose=None;old=None;minio_process=None;project='conformance-'+uuid.uuid4().hex[:12];code=2;hosts=pathlib.Path('/etc/hosts');stages=[]
 if out.exists():raise ValueError('fresh_evidence_directory_required')
 try:
  if args.minio_binary and not args.minio_provenance:raise ValueError('minio_provenance_required')
  private,compose=prepare(out,args.java_home,args.minio_image)
  locator=pathlib.Path(args.locator).resolve();locator.parent.mkdir(parents=True,exist_ok=True);os.chmod(locator.parent,0o700)
  backup=locator.parent/'hosts.backup';backup.write_text(hosts.read_text());os.chmod(backup,0o600)
  locator.write_text(json.dumps({'project':project,'private':str(private),'compose':str(compose),'hosts_backup':str(backup),'output':str(out),'process_groups':[]}));os.chmod(locator,0o600)
  os.environ['CONFORMANCE_RUN_LOCATOR']=str(locator)
  cmd=['docker','compose','-p',project,'-f',str(compose)]
  def dc(*arguments,timeout=240):
   r=owned_run(cmd+list(arguments),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
   if r.returncode:raise ValueError('compose_command_failed')
   return r.stdout
  stages.append('compose_validate');dc('config','--quiet',timeout=30);old=hosts.read_text();owned_run(['sudo','tee','-a',str(hosts)],input=b'\n127.0.0.1 certify.local.test esignet.local.test suite verify.local.test\n',stdout=subprocess.DEVNULL,check=True)
  dc('up','-d',timeout=300);stages.append('boot_requested')
  import requests
  s=requests.Session();s.verify=str(private/'tls-ca.pem');s.trust_env=False
  sys.path.insert(0,str(ROOT/'smoke/alpha-suite'));from readiness import wait
  for origin in ('certify','esignet','suite'):
   stages.append('readiness_'+origin);wait(s,origin,out,cmd,cap=180)
  sys.path.insert(0,str(ROOT/'smoke/verify-final'));from preflight import wait as verify_wait
  stages.append('verify_preflight')
  (out/'verify-preflight.json').write_text(json.dumps(verify_wait(private/'tls-ca.pem')))
  # Schema service must have succeeded, independently of HTTPreadiness.
  r=owned_run(cmd+['ps','-a','-q','verify-schema'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20);cid=r.stdout.decode().strip()
  if not cid:raise ValueError('verify_schema_container_missing')
  if r.returncode!=0:raise ValueError('verify_schema_query_failed')
  inspected=owned_run(['docker','inspect',cid],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
  if inspected.returncode!=0:raise ValueError('verify_schema_inspect_failed')
  status=json.loads(inspected.stdout)[0]['State']
  if status.get('Status')!='exited' or status.get('ExitCode')!=0 or status.get('Running'):raise ValueError('verify_schema_not_passed')
  dc('exec','-T','tls-gateway','nginx','-t',timeout=20)
  stages.append('local_minio')
  from local_minio import create_bucket
  s3=private/'local-s3.properties'
  if args.minio_binary:
   from local_minio import start_binary
   minio_process,s3=start_binary(private,args.minio_binary,args.minio_provenance)
  create_bucket(s3)
  # Exactsynthetic issuer setup reused, no prodidentity/accounts.
  stages.append('issuer_setup')
  dto=json.loads((ROOT/'smoke/alpha-init/mdl-credential-config.json').read_text());base='https://certify.local.test:8443/v1/certify/credential-configurations'
  r=s.post(base,json=dto,timeout=20);body=r.json()
  if r.status_code!=201 or body.get('id')!='DrivingLicenseCredential':raise ValueError('issuer_configuration_create')
  r=s.get(base+'/DrivingLicenseCredential',timeout=20)
  if r.status_code!=200 or r.json().get('credentialConfigKeyId')!='DrivingLicenseCredential':raise ValueError('issuer_configuration_readback')
  sys.path.insert(0,str(ROOT/'smoke/alpha-direct'));from issue import seed
  seed()
  from official_driver import Driver
  config=Driver(private/'tls-ca.pem',out).configuration(out);cf=private/'issuer-suite-config.json';cf.write_text(json.dumps(config));os.chmod(cf,0o600)
  from suite_contract import VARIANT
  vf=private/'issuer-variants.json';vf.write_text(json.dumps(VARIANT));os.chmod(vf,0o600)
  verify=json.loads((private/'verify-invocation.json').read_text());run=verify['run_id'].removesuffix('-verify')
  certify=dict(verify,env_endpoint='https://certify.local.test:8443',component='certify',config=str(cf),variants=str(vf),run_id=run+'-certify',module='oid4vci-1_0-issuer-happy-flow',evidence_dir=str(out/'certify-evidence'))
  codes={}
  for component,manifest,cp in [('certify',certify,args.certify_classpath),('verify',verify,args.verify_classpath)]:
   stages.append('native_'+component)
   try:codes[component]=invoke(component,cp,str(pathlib.Path(args.java_home)/'bin/java'),manifest,out/component,s3,timeout=1560 if os.environ.get('CONFORMANCE_REVIEW_WINDOW') and component=='verify' else 600,extra_env={'GITHUB_TOKEN':review_token} if review_token and component=='verify' else None)
   except Exception:
    codes[component]=2
    (out/(component+'-invoke-error.json')).write_text(json.dumps({'component':component,'category':'native_invocation_failure','raw_error_retained':False}))
  doc={'run':{'id':run},'native_exit_codes':codes,'scope':'selected issuer/Verify happyflows, not full plans/certification'}
  for component in codes:
   f=out/component/'conformance-results.json'
   if f.exists():doc[component]=json.loads(f.read_text()).get(component,[])
   else:doc[component]=[{'module':'selected-happyflow','test_id':'','status':'HARNESS_ERROR','result':None,'harness_category':'native_result_missing'}]
  stages.append('combined_report')
  (out/'combined-results.json').write_text(json.dumps(doc,indent=2));sys.path.insert(0,str(ROOT/'scripts'));from report_summary import render
  (out/'project-summary.html').write_text(render(doc));code=0 if all(c==0 for c in codes.values()) else 1
 except Exception as exc:
  out.mkdir(exist_ok=True);(out/'failure.json').write_text(json.dumps({'stage':stages[-1] if stages else 'prepare','error_class':type(exc).__name__,'raw_error_retained':False}));code=2
 finally:
  result=cleanup(project,compose,old,hosts,private,minio_process,out)
  if not result.get('cleanup_verified'):code=2
 return code
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--locator',required=True);p.add_argument('--java-home',required=True);group=p.add_mutually_exclusive_group(required=True);group.add_argument('--minio-image');group.add_argument('--minio-binary');p.add_argument('--minio-provenance');p.add_argument('--certify-classpath',required=True);p.add_argument('--verify-classpath',required=True);a=p.parse_args();signal.signal(signal.SIGTERM,lambda s,f:(_ for _ in ()).throw(SystemExit(143)));sys.exit(main(a))
