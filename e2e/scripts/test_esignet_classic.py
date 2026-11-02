"""Local contract test for esignet_classic.py: a stub server validates every
request shape against the v1.8.0 DTOs (AuthorizationController/OAuthController)
and feeds realistic responses; the assertion JWT is signature-verified.
Run: python e2e/scripts/test_esignet_classic.py  (no external services)"""
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "e2e/scripts")
from esignet_classic import EsignetClassic, redact, gen_client_key

BASE = "http://127.0.0.1:18123"
ISSUER = "http://esignet:8088"
CLIENT_ID = "contract-client"
REDIRECT = "http://localhost:18080/callback"
INDIVIDUAL = "1774231323"

seen = {}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _check_csrf(self):
        # every POST after the initial csrf fetch must carry an XOR-masked
        # X-XSRF-TOKEN: base64url(salt || salt XOR raw), matching Spring
        # Security 6.2 XorCsrfTokenRequestAttributeHandler semantics.
        if self.path != "/v1/esignet/csrf/token":
            import base64 as b64
            raw = b"csrf-123"
            h = self.headers.get("X-XSRF-TOKEN", "")
            ok = False
            try:
                b = b64.urlsafe_b64decode(h)
                ok = len(b) == 2 * len(raw) and                     bytes(x ^ y for x, y in zip(b[:len(raw)], b[len(raw):])) == raw
            except Exception:
                ok = False
            check(ok, f"missing/wrong XOR-masked X-XSRF-TOKEN on POST {self.path}")

    def do_GET(self):
        if self.path == "/v1/esignet/csrf/token":
            body = json.dumps({"parameterName": "_csrf", "token": "csrf-123",
                               "headerName": "X-XSRF-TOKEN"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", "XSRF-TOKEN=csrf-123; Path=/")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send({"errors": [{"errorCode": "unknown_path"}]}, 404)

    def _json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self._check_csrf()
        if self.path == "/v1/esignet/client-mgmt/oauth-client":
            req = self._json()
            check("requestTime" in req, "missing requestTime")
            r = req["request"]
            for k in ("clientId", "clientName", "publicKey", "relyingPartyId",
                      "userClaims", "authContextRefs", "logoUri", "redirectUris",
                      "grantTypes", "clientAuthMethods"):
                check(k in r, f"client reg missing {k}")
            check(r["clientAuthMethods"] == ["private_key_jwt"], "auth methods")
            check(r["publicKey"]["kty"] == "EC", "public key not a JWK map")
            seen["register"] = r
            self._send({"response": {"clientId": r["clientId"], "status": "ACTIVE"}})

        elif self.path == "/v1/esignet/authorization/oauth-details":
            r = self._json()["request"]
            check(r["responseType"] == "code", "responseType")
            check(r["clientId"] == CLIENT_ID and r["redirectUri"] == REDIRECT, "ids")
            check(isinstance(r.get("acrValues"), str), "acrValues must be a space-separated string")
            seen["details"] = r
            resp = {
                "transactionId": "txn-1",
                "authFactors": [[{"type": "PWD", "format": "alpha-numeric"}]],
                "authorizeScopes": ["openid", "sample_vc_mdoc"],
                "essentialClaims": ["name"],
                "voluntaryClaims": ["email"],
            }
            seen["details_resp"] = resp
            self._send({"response": resp})

        elif self.path == "/v1/esignet/authorization/authenticate":
            import base64 as b64, hashlib
            expected = b64.urlsafe_b64encode(hashlib.sha256(
                json.dumps(seen["details_resp"], separators=(",", ":"), ensure_ascii=False).encode()
            ).digest()).decode().rstrip("=")
            check(self.headers.get("oauth-details-key") == "txn-1", "oauth-details-key header")
            check(self.headers.get("oauth-details-hash") == expected, "oauth-details-hash header")
            r = self._json()["request"]
            check(r["transactionId"] == "txn-1", "transactionId")
            check(r["individualId"] == INDIVIDUAL, "individualId")
            ch = r["challengeList"][0]
            check(ch == {"authFactorType": "PWD", "challenge": "Mosip@123",
                         "format": "alpha-numeric"}, f"challenge shape: {ch}")
            seen["authn"] = r
            self._send({"response": {"transactionId": "txn-1", "authStatus": True}})

        elif self.path == "/v1/esignet/authorization/auth-code":
            check(self.headers.get("oauth-details-key") == "txn-1", "oauth-details-key header (auth-code)")
            check(self.headers.get("oauth-details-hash"), "oauth-details-hash header (auth-code)")
            r = self._json()["request"]
            check(r["transactionId"] == "txn-1", "auth-code transactionId")
            check(set(r["acceptedClaims"]) == {"name", "email"}, "claims echoed")
            check(r["permittedAuthorizeScopes"] == ["openid", "sample_vc_mdoc"], "scopes echoed")
            seen["authcode"] = r
            self._send({"response": {"code": "code-abc", "redirectUri": REDIRECT}})

        elif self.path == "/v1/esignet/oauth/token":
            n = int(self.headers.get("Content-Length", 0))
            form = dict(urllib.parse.parse_qsl(self.rfile.read(n).decode()))
            check(form["grant_type"] == "authorization_code", "grant_type")
            check(form["code"] == "code-abc", "code")
            check(form["client_id"] == CLIENT_ID, "client_id")
            assertion = form["client_assertion"]
            h, p, sig = assertion.split(".")
            import base64
            payload = json.loads(base64.urlsafe_b64decode(p + "=="))
            check(payload["iss"] == payload["sub"] == CLIENT_ID, "assertion iss/sub")
            check(payload["aud"] == ISSUER, f"assertion aud={payload['aud']}")
            hdr = json.loads(base64.urlsafe_b64decode(h + "=="))
            check(hdr.get("kid"), "assertion kid present")
            # verify ES256 signature (raw R||S) against the registered public key
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
            pub_jwk = seen["register"]["publicKey"]
            x = int.from_bytes(base64.urlsafe_b64decode(pub_jwk["x"] + "=="), "big")
            y = int.from_bytes(base64.urlsafe_b64decode(pub_jwk["y"] + "=="), "big")
            pub = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
            sig_bytes = base64.urlsafe_b64decode(sig + "==")
            check(len(sig_bytes) == 64, "ES256 sig not raw R||S")
            r_n = int.from_bytes(sig_bytes[:32], "big"); s_n = int.from_bytes(sig_bytes[32:], "big")
            pub.verify(encode_dss_signature(r_n, s_n), f"{h}.{p}".encode(), ec.ECDSA(hashes.SHA256()))
            seen["token"] = payload
            self._send({"access_token": "stub-token", "token_type": "Bearer", "expires_in": 3600})
        else:
            self._send({"errors": [{"errorCode": "unknown_path"}]}, 404)


srv = HTTPServer(("127.0.0.1", 18123), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()

es = EsignetClassic(BASE, ISSUER)
_, pub_jwk, priv_jwk = gen_client_key()
# register first so the token step can verify against the registered key
es.register_client(CLIENT_ID, [REDIRECT], pub_jwk)
import base64 as _b64, json as _json
priv_pem = None
from cryptography.hazmat.primitives.asymmetric import ec as _ec
from cryptography.hazmat.primitives import serialization
d = int.from_bytes(_b64.urlsafe_b64decode(priv_jwk["d"] + "=="), "big")
priv_pem = _ec.derive_private_key(d, _ec.SECP256R1()).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()).decode()

redirect, code = es.authorization_code_flow(CLIENT_ID, REDIRECT,
                                            scope="openid sample_vc_mdoc",
                                            individual_id=INDIVIDUAL)
check(code == "code-abc", "flow code")
check("code=code-abc" in redirect and "state=" in redirect, "redirect shape")
tokens = es.exchange_code(code, CLIENT_ID, priv_pem, REDIRECT)
check(tokens["access_token"] == "stub-token", "token response")

# redaction: a JWT in a log line must be masked, header preserved
masked = redact("failed: eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4In0.AAAA bad request")
check("eyJ" not in masked and "body redacted" in masked and '"alg": "ES256"' in masked, f"redact: {masked}")

print("CONTRACT TESTS PASS: register/oauth-details/authenticate/auth-code/token + ES256 assertion verify + redaction")
