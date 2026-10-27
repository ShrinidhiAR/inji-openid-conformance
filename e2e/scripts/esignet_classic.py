"""Driver for eSignet 1.8.0 (Java line) - the classic fully-REST login API.

eSignet 1.8.0 (parity baseline for the Go-based 2.0.0) exposes the login as
plain REST, no browser and no flow/execute state machine:
  POST /v1/esignet/authorization/oauth-details  -> transactionId
  POST /v1/esignet/authorization/authenticate   -> kyc auth (mock plugin: PWD)
  POST /v1/esignet/authorization/auth-code      -> authorization code
  POST /v1/esignet/oauth/token                 -> tokens (private_key_jwt)

private_key_jwt audience (OAuthServiceImpl): the token endpoint URL OR the
issuer URL are both accepted - unlike the Go 2.0.0 image's issuer-only rule.

Grounded in mosip/esignet@v1.8.0: controllers/AuthorizationController.java,
controllers/OAuthController.java, dto/AuthRequest|AuthCodeRequest|
OAuthDetailRequest, and esignet-plugins/mock-plugin MockHelperService
(challenge factors: PWD/OTP, format "alpha-numeric"; mock OTP = 111111).
"""
import base64
import json
import os
import time
import re

import requests

from esignet import gen_client_key, client_assertion, DEFAULT_KID  # reuse key/JWS helpers

API = "/v1/esignet"

# redaction: never log a full signed token; show the decoded header only
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")


def redact(text: str) -> str:
    import base64
    def _mask(m):
        tok = m.group(0)
        try:
            hdr = json.loads(base64.urlsafe_b64decode(tok.split(".")[0] + "=="))
            return f"<JWT header={json.dumps(hdr)} body redacted>"
        except Exception:
            return "<JWT redacted>"
    return _JWT_RE.sub(_mask, str(text))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


class EsignetClassic:
    """REST driver for Java eSignet. base = origin only (http://host:port)."""

    def __init__(self, base: str, issuer: str):
        self.base = base.rstrip("/")
        self.issuer = issuer.rstrip("/")   # e.g. http://esignet:8088 (container-visible)
        self.s = requests.Session()
        self._csrf_done = False

    def _ensure_csrf(self):
        """/authorization/** is permitAll for auth but NOT csrf-ignored (observed:
        POST /authorization/oauth-details -> 403 Forbidden). The oidc-ui fetches
        /csrf/token first; mirror that: GET it once, then send X-XSRF-TOKEN."""
        if self._csrf_done:
            return
        r = self.s.get(f"{self.base}{API}/csrf/token", timeout=15)
        token = self.s.cookies.get("XSRF-TOKEN")
        try:
            token = token or r.json().get("token")
        except Exception:
            pass
        if token:
            # CsrfFilter default request handler is XorCsrfTokenRequestAttributeHandler
            # (Spring Security 6.2, verified from source): the X-XSRF-TOKEN header
            # must be base64url(salt || salt XOR rawToken), NOT the raw cookie
            # value. Observed: raw token -> 403 Forbidden on /authorization/**.
            t = token.encode()
            salt = os.urandom(len(t))
            masked = base64.urlsafe_b64encode(
                salt + bytes(a ^ b for a, b in zip(salt, t))).decode()
            self.s.headers.update({"X-XSRF-TOKEN": masked})
        self._csrf_done = True

    def _post(self, path: str, request: dict) -> requests.Response:
        self._ensure_csrf()
        r = self.s.post(f"{self.base}{API}{path}",
                        json={"requestTime": _now(), "request": request}, timeout=30)
        print(f"[esignet-classic] POST {path} -> {r.status_code}: {redact(r.text)[:500]}")
        return r

    def _unwrap(self, r: requests.Response, what: str) -> dict:
        r.raise_for_status()
        body = r.json()
        errs = body.get("errors")
        if errs:
            raise RuntimeError(f"{what} failed: {json.dumps(errs)[:400]}")
        resp = body.get("response")
        if resp is None:
            raise RuntimeError(f"{what}: no response object in {json.dumps(body)[:400]}")
        return resp

    def register_client(self, client_id: str, redirect_uris, public_jwk: dict,
                        acrs=("mosip:idp:acr:password", "mosip:idp:acr:static-code",
                              "mosip:idp:acr:generated-code"),
                        method: str = "POST", **_ignored) -> requests.Response:
        """POST /client-mgmt/oauth-client (v1 DTO). Open under the official
        application-local profile (secure-url maps emptied -> permitAll)."""
        r = self._post("/client-mgmt/oauth-client", {
            "clientId": client_id,
            "clientName": "OIDF Conformance Suite (e2e)",
            "publicKey": public_jwk,
            "relyingPartyId": client_id,
            "userClaims": ["name", "email", "picture", "gender", "birthdate"],
            "authContextRefs": list(acrs),
            "logoUri": "https://openid.net/wp-content/uploads/2023/09/logo-c3f2e0c8.png",
            "redirectUris": list(redirect_uris),
            "grantTypes": ["authorization_code"],
            "clientAuthMethods": ["private_key_jwt"],
        })
        return r

    def oauth_details(self, client_id: str, redirect_uri: str, scope: str,
                      state: str, nonce: str) -> dict:
        return self._unwrap(self._post("/authorization/oauth-details", {
            "clientId": client_id,
            "scope": scope,
            "responseType": "code",
            "redirectUri": redirect_uri,
            "state": state,
            "nonce": nonce,
            "acrValues": "mosip:idp:acr:password",  # space-separated String, not array (OAuthDetailRequest.acrValues)
        }), "oauth-details")

    def authenticate(self, transaction_id: str, individual_id: str,
                     password: str = "Mosip@123") -> dict:
        return self._unwrap(self._post("/authorization/authenticate", {
            "transactionId": transaction_id,
            "individualId": individual_id,
            "challengeList": [
                {"authFactorType": "PWD", "challenge": password, "format": "alpha-numeric"},
            ],
        }), "authenticate")

    def auth_code(self, transaction_id: str, accepted_claims, permitted_scopes) -> dict:
        return self._unwrap(self._post("/authorization/auth-code", {
            "transactionId": transaction_id,
            "acceptedClaims": list(accepted_claims),
            "permittedAuthorizeScopes": list(permitted_scopes),
        }), "auth-code")

    def exchange_code(self, code: str, client_id: str, private_pem: str,
                      redirect_uri: str, kid: str = DEFAULT_KID) -> dict:
        # aud: issuer URL accepted (OAuthServiceImpl allows token endpoint URL
        # or issuer). Use the issuer - stable across endpoint layout changes.
        self._ensure_csrf()
        r = self.s.post(f"{self.base}{API}/oauth/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion(private_pem, client_id, self.issuer, kid),
        }, timeout=30)
        print(f"[esignet-classic] token -> {r.status_code}: {redact(r.text)[:300]}")
        r.raise_for_status()
        return r.json()

    def authorization_code_flow(self, client_id: str, redirect_uri: str,
                                scope: str = "openid", individual_id: str = "1774231323",
                                password: str = "Mosip@123"):
        """Full scripted classic flow; returns (redirect_uri_with_code, code)."""
        import uuid
        state = "e2e-" + uuid.uuid4().hex[:12]
        details = self.oauth_details(client_id, redirect_uri, scope, state, uuid.uuid4().hex)
        tid = details["transactionId"]
        print(f"[esignet-classic] oauth-details: authFactors={json.dumps(details.get('authFactors'))[:200]}")
        self.authenticate(tid, individual_id, password)
        claims = list(dict.fromkeys(
            (details.get("essentialClaims") or []) + (details.get("voluntaryClaims") or [])))
        ac = self.auth_code(tid, claims, details.get("authorizeScopes") or [])
        code = ac["code"]
        redirect = ac.get("redirectUri") or redirect_uri
        sep = "&" if "?" in redirect else "?"
        return f"{redirect}{sep}code={code}&state={state}", code
