"""Generate a fresh TEST mDL signer into a private runtime config, never evidence."""
import base64,datetime,os,pathlib,shutil,tempfile
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

def prepare(source,public_out):
    root=pathlib.Path(tempfile.mkdtemp(prefix='alpha-private-'));os.chmod(root,0o700)
    config=root/'config';shutil.copytree(source,config)
    key=ec.generate_private_key(ec.SECP256R1());now=datetime.datetime.now(datetime.timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Ephemeral synthetic mDL TEST issuer')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(hours=2)).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),True).sign(key,hashes.SHA256()))
    private=key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    value=base64.b64encode(private).decode()+'||'+base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
    p=config/'certify-mock-mdl.properties';s=p.read_text();needle='mosip.certify.mock.mdoc.issuer-key-cert='
    lines=s.splitlines();assert sum(x.startswith(needle) for x in lines)==1
    p.write_text('\n'.join(needle+value if x.startswith(needle) else x for x in lines)+'\n')
    for f in config.iterdir():os.chmod(f,0o600)
    public_out=pathlib.Path(public_out);public_out.mkdir(parents=True,exist_ok=True)
    (public_out/'test-issuer-anchor.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return root,cert
