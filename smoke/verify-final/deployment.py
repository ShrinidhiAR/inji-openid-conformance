"""Extend an owned disposable model only. No startup, global ports or shared DB."""
import pathlib,json,os,datetime,base64
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
HERE=pathlib.Path(__file__).resolve().parent
VARIANT={'vp_profile':'plain_vp','credential_format':'sd_jwt_vc','client_id_prefix':'redirect_uri','response_mode':'direct_post','request_method':'url_query'}
def signing_config(private,public):
 now=datetime.datetime.now(datetime.timezone.utc);key=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Ephemeral synthetic TEST SDJWT signer')])
 cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).sign(key,hashes.SHA256())
 nums=key.private_numbers();b64=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=').decode();n=lambda n:b64(n.to_bytes(32,'big'))
 jwk={'kty':'EC','crv':'P-256','alg':'ES256','use':'sig','x':n(nums.public_numbers.x),'y':n(nums.public_numbers.y),'d':n(nums.private_value),'x5c':[base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()]}
 config=pathlib.Path(private)/'verify-suite-config.json';config.write_text(json.dumps({'description':'Bounded synthetic TEST Final/DCQL backend API happyflow','credential':{'signing_jwk':jwk}}));os.chmod(config,0o600)
 variants=pathlib.Path(private)/'verify-variants.json';variants.write_text(json.dumps(VARIANT));os.chmod(variants,0o600)
 (pathlib.Path(public)/'sdjwt-test-signer.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM));return config,variants

def augment(model,private):
 services=model['services'];assert not any(k.startswith('verify-') for k in services)
 db=str(HERE/'db');p=str(pathlib.Path(private).resolve());image=json.loads((HERE/'image-lock.json').read_text())['image']
 services['verify-db']={'image':'postgres:15','environment':{'POSTGRES_PASSWORD':'synthetic-local-test','POSTGRES_DB':'inji_verify'},'volumes':[db+':/bundle:ro',db+'/init.sql:/docker-entrypoint-initdb.d/00-init.sql:ro'],'healthcheck':{'test':['CMD-SHELL','pg_isready -h 127.0.0.1 -U postgres -d inji_verify'],'interval':'5s','retries':20},'networks':['e2e-net']}
 # Run readonly schemaassertions independently before app boots.
 services['verify-schema']={'image':'postgres:15','environment':{'PGHOST':'verify-db','PGUSER':'postgres','PGPASSWORD':'synthetic-local-test','PGDATABASE':'inji_verify'},'volumes':[db+':/bundle:ro'],'entrypoint':['psql','-f','/bundle/assert-schema.sql'],'depends_on':{'verify-db':{'condition':'service_healthy'}},'networks':['e2e-net']}
 services['verify-app']={'image':image,'user':'root','environment':{'active_profile_env':'default','DATABASE_HOST':'verify-db','DATABASE_PORT':'5432','DATABASE_NAME':'inji_verify','DATABASE_SCHEMA':'verify','DATABASE_USERNAME':'postgres','DATABASE_PASSWORD':'synthetic-local-test','VERIFY_CONTEXT_PATH':'/v1/verify','INJI_VP_SUBMISSION_BASE_URL':'https://verify.local.test:8443/v1/verify','INJI_VERIFY_REDIRECT_URI':'https://verify.local.test:8443/v1/verify','JAVA_TOOL_OPTIONS':'-Djavax.net.ssl.trustStore=/runtime/truststore -Djavax.net.ssl.trustStorePassword=changeit'},'volumes':[p+'/truststore:/runtime/truststore:ro'],'depends_on':{'verify-schema':{'condition':'service_completed_successfully'}},'networks':['e2e-net']}
 gateway=services['tls-gateway'];gateway['networks']['e2e-net']['aliases'].append('verify.local.test');gateway['depends_on'].append('verify-app')
 return model
