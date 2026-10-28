"""Runtime-only local TEST IACA and document signer, supported single-leaf plugin input.
No change to plugin: it takes one leaf certificate; root is configured out-of-band.
"""
import base64,datetime,pathlib,os
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

def provision(private_config,public):
    now=datetime.datetime.now(datetime.timezone.utc)
    root_key=ec.generate_private_key(ec.SECP256R1());leaf_key=ec.generate_private_key(ec.SECP256R1())
    root_name=x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME,'IN'),x509.NameAttribute(NameOID.COMMON_NAME,'Local synthetic TEST IACA')])
    leaf_name=x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME,'IN'),x509.NameAttribute(NameOID.COMMON_NAME,'Local synthetic TEST Document Signer')])
    common=lambda subject,issuer,pub:x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(pub).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
    root=(common(root_name,root_name,root_key.public_key()).add_extension(x509.BasicConstraints(ca=True,path_length=0),True).add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),True).add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),False).sign(root_key,hashes.SHA256()))
    leaf=(common(leaf_name,root_name,leaf_key.public_key()).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),True).add_extension(x509.ExtendedKeyUsage([x509.ObjectIdentifier('1.0.18013.5.1.2')]),True).add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),False).sign(root_key,hashes.SHA256()))
    value=base64.b64encode(leaf_key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())).decode()+'||'+base64.b64encode(leaf.public_bytes(serialization.Encoding.DER)).decode()
    p=pathlib.Path(private_config)/'certify-mock-mdl.properties';lines=p.read_text().splitlines();needle='mosip.certify.mock.mdoc.issuer-key-cert='
    if sum(x.startswith(needle) for x in lines)!=1:raise ValueError('ambiguous signer property')
    p.write_text('\n'.join(needle+value if x.startswith(needle) else x for x in lines)+'\n');os.chmod(p,0o600)
    public=pathlib.Path(public);(public/'mdoc-test-iaca.pem').write_bytes(root.public_bytes(serialization.Encoding.PEM));(public/'mdoc-test-leaf.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    return root,leaf
