"""Prepare only. Caller owns boot, cleanup, /etc/hosts restoration and gate."""
import json,os,pathlib,sys,yaml
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'alpha-direct'))
from runtime_signer import prepare
from run_once import bundle
from tls_config import tls,augment,CERTIFY,AS
from mdoc_signer import provision

def prepare_suite(out,java_home,include_verify=False):
 out=pathlib.Path(out);out.mkdir(exist_ok=False);private,_=prepare(ROOT/'smoke/alpha-init/config',out)
 # Discard selfsigned baseline public cert; new suite uses independent TEST IACA+leaf.
 (out/'test-issuer-anchor.pem').unlink()
 provision(private/'config',out)
 names=('certify.local.test','esignet.local.test','suite','verify.local.test') if include_verify else ('certify.local.test','esignet.local.test','suite')
 targets=('certify-app:8090','esignet-gateway:8088','suite-server:8080','verify-app:8080') if include_verify else None
 tls(private,out,java_home,names,targets)
 p=private/'config/certify-default.properties';lines=p.read_text().splitlines()
 values={'mosip.certify.domain.url':CERTIFY,'mosip.certify.authorization.url':AS,'mosip.certify.authn.issuer-uri':AS,'mosip.certify.authn.jwk-set-uri':AS+'/v1/esignet/oauth/.well-known/jwks.json','mosip.certify.authn.allowed-audiences':"{ '"+AS+"/v1/esignet/vci/credential' }"}
 for key,value in values.items():
  if sum(x.startswith(key+'=') for x in lines)!=1:raise ValueError('ambiguous runtime property')
  lines=[key+'='+value if x.startswith(key+'=') else x for x in lines]
 p.write_text('\n'.join(lines)+'\n');os.chmod(p,0o600)
 p=private/'config/certify-mock-mdl.properties';lines=p.read_text().splitlines();lines=[x for x in lines if not x.startswith('mosip.certify.domain.url=')];p.write_text('\n'.join(lines)+'\n');os.chmod(p,0o600)
 compose,model=bundle(private);lock=json.loads((HERE/'image-lock.json').read_text());model=augment(model,private,lock['image'])
 e=model['services']['esignet-app']['environment'];pairs={'MOSIP_ESIGNET_DOMAIN_URL':AS,'MOSIP_ESIGNET_JWKS_URI':AS+'/v1/esignet/oauth/.well-known/jwks.json','MOSIP_ESIGNET_CREDENTIAL_SCOPE_RESOURCE_MAPPING':"{'sample_vc_mdoc': '"+AS+"/v1/esignet/vci/credential'}"}
 for key,value in pairs.items():
  if sum(x.startswith(key+'=') for x in e)!=1:raise ValueError('ambiguous AS runtime property')
  e[:]=[key+'='+value if x.startswith(key+'=') else x for x in e]
 compose.write_text(yaml.safe_dump(model));os.chmod(compose,0o600)
 return private,compose
