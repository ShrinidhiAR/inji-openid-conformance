"""Verify a synthetic mDL in memory, pinned to this run's public TEST anchor.
This is cryptographic integrity against an ephemeral test signer, not issuer trust.
"""
import base64,datetime,hashlib,cbor2
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

def verify(credential,anchor_pem,holder_jwk=None):
    m=cbor2.loads(base64.urlsafe_b64decode(credential+'='*(-len(credential)%4)))
    if m.get('docType')!='org.iso.18013.5.1.mDL':raise ValueError('wrong document type')
    signed=m['issuerSigned'];ia=signed['issuerAuth']
    if isinstance(ia,cbor2.CBORTag):
        if ia.tag!=18:raise ValueError('unexpected COSE tag')
        ia=ia.value
    if not isinstance(ia,(list,tuple)) or len(ia)!=4:raise ValueError('wrong COSE structure')
    protected,unprotected,payload,sig=ia
    if cbor2.loads(protected).get(1)!=-7 or len(sig)!=64:raise ValueError('expected ES256 raw signature')
    chain=unprotected[33];der=chain[0] if isinstance(chain,(list,tuple)) else chain
    if isinstance(der,cbor2.CBORTag):der=der.value
    cert=x509.load_der_x509_certificate(bytes(der));anchor=x509.load_pem_x509_certificate(anchor_pem)
    if cert.public_bytes(serialization.Encoding.DER)!=anchor.public_bytes(serialization.Encoding.DER):raise ValueError('embedded signer does not match run anchor')
    now=datetime.datetime.now(datetime.timezone.utc)
    if not cert.not_valid_before_utc<=now<=cert.not_valid_after_utc:raise ValueError('signer validity failed')
    pub=cert.public_key()
    if not isinstance(pub,ec.EllipticCurvePublicKey) or not isinstance(pub.curve,ec.SECP256R1):raise ValueError('wrong signer curve')
    pub.verify(encode_dss_signature(int.from_bytes(sig[:32],'big'),int.from_bytes(sig[32:],'big')),cbor2.dumps(['Signature1',protected,b'',payload]),ec.ECDSA(hashes.SHA256()))
    mso=cbor2.loads(payload)
    if isinstance(mso,cbor2.CBORTag):
        if mso.tag!=24:raise ValueError('unexpected MSO tag')
        mso=cbor2.loads(mso.value)
    if mso.get('docType')!=m['docType'] or mso.get('digestAlgorithm')!='SHA-256':raise ValueError('wrong MSO contract')
    validity=mso.get('validityInfo',{})
    if any(not isinstance(validity.get(k),datetime.datetime) for k in ('signed','validFrom','validUntil')):raise ValueError('missing MSO validity')
    if not validity['signed']<=now or not validity['validFrom']<=now<=validity['validUntil']:raise ValueError('MSO time validity failed')
    if holder_jwk is not None:
        dk=mso.get('deviceKeyInfo',{}).get('deviceKey',{})
        decode=lambda v:base64.urlsafe_b64decode(v+'='*(-len(v)%4))
        if dk.get(1)!=2 or dk.get(-1)!=1 or dk.get(-2)!=decode(holder_jwk['x']) or dk.get(-3)!=decode(holder_jwk['y']):raise ValueError('MSO holder key mismatch')
    total=0
    for ns,items in signed['nameSpaces'].items():
        seen=set()
        for item in items:
            if not isinstance(item,cbor2.CBORTag) or item.tag!=24:raise ValueError('unexpected issuer item encoding')
            inner=cbor2.loads(item.value);idx=inner['digestID']
            if idx in seen:raise ValueError('duplicate digest ID')
            seen.add(idx)
            if mso['valueDigests'][ns].get(idx)!=hashlib.sha256(cbor2.dumps(item)).digest():raise ValueError('issuer item digest mismatch')
            total+=1
        if seen!=set(mso['valueDigests'][ns]):raise ValueError('incomplete namespace digests')
    if set(signed['nameSpaces'])!=set(mso['valueDigests']) or total==0:raise ValueError('incomplete namespaces')
    return {'signature_verified':True,'embedded_cert_matches_run_anchor':True,'digest_count':total,'all_digests_verified':True,'mso_time_valid':True,'holder_key_verified':holder_jwk is not None,'trust':'ephemeral TEST signer only'}
