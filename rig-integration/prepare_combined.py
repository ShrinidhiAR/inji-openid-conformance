"""PREPARE ONLY: compose, freshkeys and invocation manifests; starts nothing.

Caller must own one disposable stack, private cleanup and approval before run.
"""
import pathlib,sys,json,os,yaml,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
def prepare(out,java_home,minio_image=None):
 sys.path.insert(0,str(ROOT/'smoke/alpha-suite'));from prepare_runtime import prepare_suite
 private,compose=prepare_suite(out,java_home,include_verify=True)
 try:
  sys.path.insert(0,str(ROOT/'smoke/verify-final'));from deployment import augment,signing_config
  model=yaml.safe_load(compose.read_text());augment(model,private);config,variants=signing_config(private,out)
  if minio_image:
   from local_minio import augment as minio
   minio(model,private,minio_image)
  compose.write_text(yaml.safe_dump(model));os.chmod(compose,0o600)
  run='combined-'+uuid.uuid4().hex
  invocation={'env_endpoint':'https://verify.local.test:8443','verify_service_url':'https://verify.local.test:8443','component':'verify','runner':str(ROOT/'scripts/conformance_runner.py'),'suite_url':'https://suite:8443','ca_file':str(private/'tls-ca.pem'),'config':str(config),'variants':str(variants),'run_id':run+'-verify','module':'oid4vp-1final-verifier-happy-flow','synthetic_handoffs':True,'evidence_dir':str(pathlib.Path(out)/'verify-evidence')}
  if os.environ.get('CONFORMANCE_REVIEW_WINDOW'):
   window=int(os.environ['CONFORMANCE_REVIEW_WINDOW']);assert 0<window<=600 and os.environ.get('CONFORMANCE_REVIEW_DIR');invocation['review_window']=window;invocation['review_dir']=os.environ['CONFORMANCE_REVIEW_DIR']
  (private/'verify-invocation.json').write_text(json.dumps(invocation));os.chmod(private/'verify-invocation.json',0o600)
  (pathlib.Path(out)/'prepared-scope.json').write_text(json.dumps({'id':run,'status':'prepared not started','components':['certify','verify','officialsuite'],'verify_profile':'Final/DCQL SDJWT plain_vp redirect_uri direct_post url_query','minio_configured':bool(minio_image),'native_rig_runtime_verified':False,'main_untouched':True},indent=2))
  return private,compose
 except Exception:
  import shutil
  shutil.rmtree(private);raise
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--java-home',required=True);p.add_argument('--minio-image');a=p.parse_args();private,compose=prepare(a.output,a.java_home,a.minio_image);print('PRIVATE_PREPARATION '+str(private));print('COMPOSE '+str(compose))
