"""Verify an issued mso_mdoc credential artifact (stage3 evidence).

Checks, each reported separately:
  1. COSE_Sign1 issuerAuth signature verifies against the embedded x5c cert
     (cryptographic validity of THIS credential).
  2. MSO docType == top-level docType.
  3. Every IssuerSignedItem digest matches MSO valueDigests (namespace
     consistency per ISO 18013-5).
  4. Issuer cert facts (subject/issuer/validity/curve). A self-signed test
     key proves cryptographic integrity only - NOT external issuer trust.

Exit nonzero (fail-closed) on any failed check.
"""
import base64
import hashlib
import json
import sys

import cbor2
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

COSE_ALG = { -7: ("ES256", ec.SECP256R1, hashes.SHA256) }

failures = []

def check(ok, label):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)

doc = json.load(open("stage3-evidence/credential-response.json"))
raw = base64.urlsafe_b64decode(doc["credential"] + "=" * (-len(doc["credential"]) % 4))
m = cbor2.loads(raw)
check(m.get("docType") == "org.iso.18013.5.1.mDL", f"top-level docType = {m.get('docType')!r}")
issuer_signed = m["issuerSigned"]
ia = issuer_signed["issuerAuth"]
if isinstance(ia, cbor2.CBORTag):
    check(ia.tag == 18, f"issuerAuth CBOR tag = {ia.tag} (18 = COSE_Sign1)")
    ia = ia.value
protected, unprotected, payload, signature = ia

ph = cbor2.loads(protected)
alg = ph.get(1)
check(alg in COSE_ALG, f"COSE alg = {alg} (-7 = ES256)")
_, curve, hash_alg = COSE_ALG[alg]

x5c = unprotected.get(33)
check(x5c is not None, "x5c present in unprotected header")
if isinstance(x5c, (list, tuple)):
    x5c = x5c[0]
if isinstance(x5c, cbor2.CBORTag):   # some encoders wrap x5c in tag(24)
    x5c = x5c.value
cert = x509.load_der_x509_certificate(bytes(x5c))
self_signed = cert.subject == cert.issuer
print(f"issuer cert: subject={cert.subject.rfc4514_string()} issuer={cert.issuer.rfc4514_string()}")
print(f"  validity {cert.not_valid_before_utc} .. {cert.not_valid_after_utc}, self_signed={self_signed}")
print("  NOTE: self-signed ephemeral TEST issuer key - proves cryptographic integrity only, NOT external issuer trust")

# 1. COSE_Sign1 signature
sig_structure = cbor2.dumps(["Signature1", protected, b"", payload])
try:
    cert.public_key().verify(signature, sig_structure, ec.ECDSA(hash_alg()))
    check(True, "COSE_Sign1 signature verifies against embedded x5c cert")
except InvalidSignature:
    check(False, "COSE_Sign1 signature verifies against embedded x5c cert")

# 2. MSO docType consistency
mso = cbor2.loads(payload)
check(mso.get("docType") == m.get("docType"), f"MSO docType == top-level docType ({mso.get('docType')!r})")
print(f"MSO: version={mso.get('version')!r} digestAlgorithm={mso.get('digestAlgorithm')!r} "
      f"validityInfo={mso.get('validityInfo')}")

# 3. namespace digest consistency
digest_name = mso.get("digestAlgorithm", "SHA-256")
hashfn = {"SHA-256": hashlib.sha256, "SHA-384": hashlib.sha384, "SHA-512": hashlib.sha512}[digest_name]
vd = mso.get("valueDigests", {})
total, matched = 0, 0
for ns, items in (issuer_signed.get("nameSpaces") or {}).items():
    ids = []
    for item in items:
        enc = cbor2.dumps(item)                      # tag(24) + inner bytes, byte-identical re-encode
        inner = cbor2.loads(item.value if isinstance(item, cbor2.CBORTag) else item)
        total += 1
        ok = vd.get(ns, {}).get(inner["digestID"]) == hashfn(enc).digest()
        matched += ok
        ids.append(f"{inner['elementIdentifier']}:{'ok' if ok else 'MISMATCH'}")
    print(f"namespace {ns}: {ids}")
check(total > 0 and matched == total, f"namespace digests match MSO valueDigests ({matched}/{total})")

report = {
    "format": "mso_mdoc",
    "docType": m.get("docType"),
    "cose_alg": alg,
    "issuer_cert": {
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "self_signed": self_signed,
        "not_valid_before": str(cert.not_valid_before_utc),
        "not_valid_after": str(cert.not_valid_after_utc),
        "trust_note": "self-signed ephemeral TEST issuer key; cryptographic integrity only, no external trust chain",
    },
    "namespaces": {ns: [cbor2.loads(i.value if isinstance(i, cbor2.CBORTag) else i)["elementIdentifier"]
                        for i in items] for ns, items in (issuer_signed.get("nameSpaces") or {}).items()},
    "digest_matches": f"{matched}/{total}",
    "validity_info": {k: str(v) for k, v in (mso.get("validityInfo") or {}).items()},
    "checks_failed": failures,
}
with open("stage3-evidence/verification-report.json", "w") as fh:
    json.dump(report, fh, indent=1)
if failures:
    print("::error::mDL verification failed: " + "; ".join(failures))
    sys.exit(1)
print("VERIFY OK: COSE signature + MSO docType + all namespace digests verified")
