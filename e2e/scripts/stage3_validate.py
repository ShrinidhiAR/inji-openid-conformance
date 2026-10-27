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
from mdl_config import ensure_mdl_config
mdoc_id, _issuer = ensure_mdl_config(CERTIFY)
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
# debug the certify /nonce 401: print JWT header+claims (never the signature),
# plus current time, to compare against certify's decoder expectations.
import base64 as _b64, json as _json
_parts = access.split(".")
if len(_parts) == 3:
    _h = _json.loads(_b64.urlsafe_b64decode(_parts[0] + "==" ))
    _p = _json.loads(_b64.urlsafe_b64decode(_parts[1] + "==" ))
    print("== access token header:", _h)
    print("== access token claims:", _p)
    print("== now:", int(time.time()))
else:
    print("== access token is NOT a JWT (opaque), parts:", len(_parts))

# debug: which jwks endpoint does this eSignet advertise, and does it serve?
oc = requests.get(f"{ESIGNET}/.well-known/openid-configuration", timeout=30).json()
jwks_uri = oc.get("jwks_uri")
print("== esignet jwks_uri:", jwks_uri)
if jwks_uri:
    probe = requests.get(jwks_uri.replace("http://esignet:8080", ESIGNET), timeout=30)
    print("== jwks probe:", probe.status_code, probe.text[:150])

# wallet proof key + c_nonce
nonce = requests.get(f"{CERTIFY}/v1/certify/nonce",
                     headers={"Authorization": f"Bearer {access}"}, timeout=30)
if nonce.status_code == 401:
    # 1. does the signature verify against the advertised jwks? (never print
    #    the token itself)
    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        jwks = requests.get(jwks_uri.replace("http://esignet:8080", ESIGNET), timeout=30).json()
        h, p, sig = access.split(".")
        hdr = json.loads(base64.urlsafe_b64decode(h + "=="))
        key = next(k for k in jwks["keys"] if k["kid"] == hdr["kid"])
        n = int.from_bytes(base64.urlsafe_b64decode(key["n"] + "=="), "big")
        e = int.from_bytes(base64.urlsafe_b64decode(key["e"] + "=="), "big")
        pub = rsa.RSAPublicNumbers(e, n).public_key()
        pad = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH) \
            if hdr["alg"] == "PS256" else padding.PKCS1v15()
        try:
            pub.verify(base64.urlsafe_b64decode(sig + "=="), (h + "." + p).encode(), pad, hashes.SHA256())
            print("== local signature check: VALID (kid", hdr["kid"][:8], ")")
        except Exception as ex:
            print("== local signature check: INVALID:", type(ex).__name__)
    except Exception as ex:
        print("== local signature check: error:", ex)
    # 2. can a container on e2e-net (like certify-app) reach the jwks url?
    import subprocess
    r = subprocess.run(["docker", "run", "--rm", "--network", "e2e-net",
                        "curlimages/curl:8.10.1", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "10", "http://esignet:8080/oauth2/jwks"],
                       capture_output=True, text=True)
    print("== container-network jwks probe:", r.stdout.strip(), r.stderr.strip()[:120])

print("nonce:", nonce.status_code, nonce.text[:200])
if nonce.status_code == 401:
    # isolate the nginx gateway: same call straight to certify-app (debug port)
    d = requests.get("http://localhost:8099/v1/certify/nonce",
                     headers={"Authorization": f"Bearer {access}"}, timeout=15)
    print("nonce direct-to-app:", d.status_code, d.text[:200])
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
# metadata URLs are container-addressed (http://certify:8090); rewrite for host-side use
cred_endpoint = md["credential_endpoint"].replace("http://certify:8090", CERTIFY)
r = requests.post(cred_endpoint, json=cred_req,
                  headers={"Authorization": f"Bearer {access}"}, timeout=60)
print("credential:", r.status_code, r.text[:400])
r.raise_for_status()
assert r.json().get("credential"), "no credential in response"
print("STAGE3 OK: local certify issued an mDL credential via scripted wallet")
