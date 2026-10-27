"""Stage 2 validation: prove the scripted eSignet authorization-code flow works
against the local eSignet 1.8.0 (Java) stack, before the conformance suite
enters the picture.

Registers a throwaway OIDC client, drives the login via eSignet's classic REST
API (oauth-details -> authenticate -> auth-code; mock identity system:
REST-seeded individual), and exchanges the resulting code for tokens with
private_key_jwt - the same legs the conformance-suite orchestrator will need.
"""
import sys
import json

sys.path.insert(0, "e2e/scripts")
from esignet_classic import EsignetClassic, gen_client_key

BASE = "http://localhost:8090"          # host-mapped esignet port (8088 in-container)
ISSUER = "http://esignet:8088"        # issuer as containers on e2e-net see it
CLIENT_ID = "e2e-stage2-client"
REDIRECT_URI = "http://localhost:18080/callback"   # nothing listens; we only need the code

es = EsignetClassic(BASE, ISSUER)

print("== openid-configuration ==")
conf = es.s.get(f"{BASE}/v1/esignet/oidc/.well-known/openid-configuration", timeout=30)
print(conf.text[:800])
conf.raise_for_status()

private_pem, public_jwk, _ = gen_client_key()
es.register_client(CLIENT_ID, [REDIRECT_URI], public_jwk)

redirect, code = es.authorization_code_flow(CLIENT_ID, REDIRECT_URI, scope="openid")
print(f"== got code == {code[:12]}... (redirect: {redirect[:120]})")

tokens = es.exchange_code(code, CLIENT_ID, private_pem, REDIRECT_URI)
print("== token response keys ==", sorted(tokens))
assert "access_token" in tokens, "no access token issued"
print("STAGE2 OK: scripted eSignet authorization-code flow works end to end")
