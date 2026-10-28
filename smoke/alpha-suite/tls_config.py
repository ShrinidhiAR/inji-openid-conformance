"""Local TEST TLS runtime config. No service started by this module."""
import datetime,os,pathlib,subprocess
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
NAMES=('certify.local.test','esignet.local.test','suite')
CERTIFY='https://'+NAMES[0]+':8443';AS='https://'+NAMES[1]+':8443';SUITE='https://'+NAMES[2]+':8443'

def tls(private,public,java_home):
    private=pathlib.Path(private);public=pathlib.Path(public);now=datetime.datetime.now(datetime.timezone.utc)
    ca=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Ephemeral local TEST transport CA')])
    root=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.public_key()),False).add_extension(x509.BasicConstraints(ca=True,path_length=0),True).add_extension(x509.KeyUsage(True,False,False,False,False,True,True,False,False),True).sign(ca,hashes.SHA256()))
    (private/'tls-ca.pem').write_bytes(root.public_bytes(serialization.Encoding.PEM));(public/'tls-ca.pem').write_bytes(root.public_bytes(serialization.Encoding.PEM))
    for host in NAMES:
        key=ec.generate_private_key(ec.SECP256R1())
        cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,host)])).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(hours=4)).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.public_key()),False).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]),False).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),False).sign(ca,hashes.SHA256()))
        (private/(host+'.key')).write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (private/(host+'.pem')).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (public/(host+'.pem')).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # Verify every fresh runtime transport chain/SAN before any service starts.
    # Do not weaken client verification to accommodate our generated certificates.
    rootcheck=subprocess.run(['openssl','verify','-x509_strict','-CAfile',str(public/'tls-ca.pem'),str(public/'tls-ca.pem')],capture_output=True)
    if rootcheck.returncode:raise ValueError('TEST transport root strict verification failed')
    for host in NAMES:
        check=subprocess.run(['openssl','verify','-x509_strict','-verify_hostname',host,'-CAfile',str(public/'tls-ca.pem'),str(public/(host+'.pem'))],capture_output=True)
        if check.returncode:raise ValueError('TEST transport leaf strict verification failed')
    # Copy normal roots and add TEST CA, rather than replacing platform trust.
    import shutil
    shutil.copyfile(pathlib.Path(java_home)/'lib/security/cacerts',private/'truststore')
    r=subprocess.run([str(pathlib.Path(java_home)/'bin/keytool'),'-importcert','-noprompt','-alias','local-test-ca','-file',str(private/'tls-ca.pem'),'-keystore',str(private/'truststore'),'-storepass','changeit'],capture_output=True)
    if r.returncode:raise RuntimeError('TEST CA import failed')
    nginx=[]
    for host,target in zip(NAMES,('certify-app:8090','esignet-gateway:8088','suite-server:8080')):
        nginx.append('server { listen 8443 ssl; server_name '+host+'; ssl_protocols TLSv1.2 TLSv1.3; ssl_certificate /runtime/'+host+'.pem; ssl_certificate_key /runtime/'+host+'.key; location / { proxy_pass http://'+target+'; proxy_set_header Host $http_host; proxy_set_header X-Forwarded-Proto https; }}')
    (private/'tls.conf').write_text('\n'.join(nginx))
    for p in private.iterdir():
        if p.is_file():os.chmod(p,0o600)
    return root

def augment(model,private,image):
    p=str(pathlib.Path(private).resolve())
    for svc in ('certify-app','esignet-app'):
        s=model['services'][svc];s.setdefault('volumes',[]).append(p+'/truststore:/runtime/truststore:ro')
        e=s['environment'];value='-Djavax.net.ssl.trustStore=/runtime/truststore -Djavax.net.ssl.trustStorePassword=changeit'
        if isinstance(e,dict):e['JAVA_TOOL_OPTIONS']=value
        else:e.append('JAVA_TOOL_OPTIONS='+value)
    model['services']['suite-mongodb']={'image':'mongo:6.0','networks':['e2e-net']}
    model['services']['suite-server']={'image':image,'environment':{'MONGODB_HOST':'suite-mongodb','BASE_URL':SUITE,'JAVA_EXTRA_ARGS':'-Dfintechlabs.devmode=true','OIDC_GOOGLE_CLIENTID':'dummy','OIDC_GOOGLE_SECRET':'dummy','OIDC_GITLAB_CLIENTID':'dummy','OIDC_GITLAB_SECRET':'dummy'},'depends_on':['suite-mongodb'],'networks':['e2e-net']}
    model['services']['tls-gateway']={'image':'nginx:1.27-alpine','volumes':[p+':/runtime:ro',p+'/tls.conf:/etc/nginx/conf.d/default.conf:ro'],'ports':['127.0.0.1:8443:8443'],'networks':{'e2e-net':{'aliases':list(NAMES)}},'depends_on':['certify-app','esignet-gateway','suite-server']}
    return model
