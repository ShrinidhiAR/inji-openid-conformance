"""Stage 3 validation: direct OID4VCI mDL issuance against the local
certify + eSignet stack - no conformance suite yet. Proves that:
  1. local certify boots with the mock-mdl plugin and serves issuer metadata,
  2. a scripted wallet can complete the eSignet login + token exchange with an
     access token certify accepts,
  3. certify issues an mso_mdoc credential for a valid proof.
The conformance suite will replay these same legs in stage 4.
"""
import sys, json, time, uuid
import urllib.parse

sys.path.insert(0, "e2e/scripts")
from esignet import Esignet, gen_client_key, _sign_es256
import requests

ESIGNET = "http://localhost:8090"
CERTIFY = "http://localhost:8088"
CLIENT_ID = "e2e-stage3-wallet"
REDIRECT_URI = "http://localhost:18080/callback"

es = Esignet(ESIGNET)

print("== certify issuer metadata ==")
meta = requests.get(f"{CERTIFY}/v1/certify/.well-known/openid-credential-issuer", timeout=30)
meta.raise_for_status()
md = meta.json()
print(json.dumps({k: md[k] for k in ("credential_issuer", "credential_endpoint") if k in md}, indent=1))
cred_configs = md.get("credential_configurations_supported", {})
print("credential configurations:", {k: v.get("format") for k, v in cred_configs.items()})
mdoc_id = next((k for k, v in cred_configs.items() if v.get("format") == "mso_mdoc"), None)
assert mdoc_id, "no mso_mdoc credential configuration advertised"
scope = cred_configs[mdoc_id].get("scope")
print(f"using credential configuration {mdoc_id} with scope {scope}")

private_pem, public_jwk, _ = gen_client_key()
es.register_client(CLIENT_ID, [REDIRECT_URI], public_jwk)

redirect, code = es.authorization_code_flow(
    CLIENT_ID, REDIRECT_URI, scope=f"openid {scope}")
print(f"== code == {code[:12]}...")

tokens = es.exchange_code(code, CLIENT_ID, private_pem, REDIRECT_URI)
access = tokens["access_token"]
print("== access token obtained ==")

# wallet proof key + c_nonce
nonce = requests.get(f"{CERTIFY}/v1/certify/nonce",
                     headers={"Authorization": f"Bearer {access}"}, timeout=30)
print("nonce:", nonce.status_code, nonce.text[:200])
c_nonce = nonce.json().get("c_nonce") if nonce.status_code == 200 else None

proof_key_pem, proof_pub_jwk, _ = gen_client_key()
now = int(time.time())
proof = _sign_es256(
    proof_key_pem,
    {"alg": "ES256", "typ": "openid4vci-proof+jwt", "jwk": proof_pub_jwk},
    {"iss": CLIENT_ID, "aud": md["credential_issuer"], "iat": now, **({"nonce": c_nonce} if c_nonce else {})})

cred_req = {
    "format": "mso_mdoc",
    "doctype": "org.iso.18013.5.1.mDL",
    "proof": {"proof_type": "jwt", "jwt": proof},
}
r = requests.post(md["credential_endpoint"], json=cred_req,
                  headers={"Authorization": f"Bearer {access}"}, timeout=60)
print("credential:", r.status_code, r.text[:400])
r.raise_for_status()
assert r.json().get("credential"), "no credential in response"
print("STAGE3 OK: local certify issued an mDL credential via scripted wallet")
