#!/usr/bin/env python3
"""Diagnostic: after one full scripted eSignet login, try token-exchange
variants against the 401 invalid_client ("Invalid client assertion") wall and
print every response verbatim. A variant that fixes the assertion consumes the
authorization code and returns 200 (or a later-stage error); variants the
server rejects keep returning invalid_client and leave the code intact, so the
sequence is self-ordering: the first non-invalid_client result identifies the
working shape."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esignet import Esignet, gen_client_key, client_assertion

ESIGNET = "http://localhost:8090"
REDIRECT = "http://localhost:18080/callback"
CLIENT_ID = "e2e-probe-client"

es = Esignet(ESIGNET)
priv, pub, _ = gen_client_key()
r = es.register_client(CLIENT_ID, [REDIRECT], pub)
if r.status_code not in (200, 201) or not (r.json().get("response") or {}):
    r = es.register_client(CLIENT_ID, [REDIRECT], pub, method="PUT")
print("[probe] registered:", r.text[:200])

redirect, code = es.authorization_code_flow(CLIENT_ID, REDIRECT)
print(f"[probe] code acquired: {code[:12]}...")

TOKEN_URL = f"{ESIGNET}/oauth2/token"
variants = [
    ("aud=internal-token-url + kid", "http://esignet:8080/oauth2/token", "e2e-key-1"),
    ("aud=issuer + kid", "http://esignet:8080", "e2e-key-1"),
    ("aud=internal-token-url, no kid", "http://esignet:8080/oauth2/token", None),
    ("aud=localhost-token-url + kid", "http://localhost:8090/oauth2/token", "e2e-key-1"),
]
for label, aud, kid in variants:
    hdr_kid = kid if kid else "e2e-key-1"
    assertion = client_assertion(priv, CLIENT_ID, aud, kid=hdr_kid)
    if kid is None:
        # strip kid from the header for the control variant
        import json as _json
        from esignet import _sign_es256
        import time as _time, uuid as _uuid
        now = int(_time.time())
        assertion = _sign_es256(priv, {"alg": "ES256", "typ": "JWT"},
                                {"iss": CLIENT_ID, "sub": CLIENT_ID, "aud": aud,
                                 "iat": now, "exp": now + 300, "jti": str(_uuid.uuid4())})
    resp = es.s.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "client_id": CLIENT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": assertion,
    }, timeout=30)
    print(f"[probe] {label}: {resp.status_code} {resp.text[:250]}")
    if resp.status_code == 200:
        print(f"[probe] WORKING VARIANT: {label}")
        break
