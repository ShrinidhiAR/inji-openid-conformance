"""Minimal eSignet 2.0 driver: client registration + REST authentication flow.

eSignet's login UI is a thin shell over REST endpoints (/flow/execute,
/oauth2/auth/callback), so the whole authorization-code login can be driven
without a browser. Used by the e2e orchestrator to complete the login leg that
OpenID conformance suite VCI issuer modules park on (Status.WAITING).

Grounded in mosip/esignet docs/esignet-openapi.yaml (esignet 2.0.0).
"""
import json
import time
import uuid
import urllib.parse

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def gen_client_key():
    """Generate an EC P-256 keypair; return (private_pem_str, public_jwk_dict, private_jwk_dict)."""
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    numbers = key.private_numbers()
    pub = numbers.public_numbers
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64u(pub.x.to_bytes(32, "big")),
        "y": _b64u(pub.y.to_bytes(32, "big")),
        "use": "sig",
        "alg": "ES256",
    }
    private_jwk = dict(public_jwk)
    private_jwk["d"] = _b64u(numbers.private_value.to_bytes(32, "big"))
    return private_pem, public_jwk, private_jwk


def _sign_es256(private_pem: str, header: dict, payload: dict) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec as _ec
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    h = _b64u(json.dumps(header).encode())
    p = _b64u(json.dumps(payload).encode())
    sig = key.sign(f"{h}.{p}".encode(), _ec.ECDSA(hashes.SHA256()))
    return f"{h}.{p}.{_b64u(sig)}"


def client_assertion(private_pem: str, client_id: str, aud: str) -> str:
    now = int(time.time())
    return _sign_es256(
        private_pem,
        {"alg": "ES256", "typ": "JWT"},
        {"iss": client_id, "sub": client_id, "aud": aud,
         "iat": now, "exp": now + 300, "jti": str(uuid.uuid4())},
    )


class Esignet:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.s = requests.Session()

    def register_client(self, client_id: str, redirect_uris, public_jwk: dict,
                        acrs=("mosip:idp:acr:password", "mosip:idp:acr:static-code",
                              "mosip:idp:acr:generated-code"),
                        method: str = "POST"):
        """POST (create) or PUT (update) /client-mgmt/oidc-client."""
        body = {
            "requestTime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "request": {
                "clientId": client_id,
                "clientName": "OIDF Conformance Suite (e2e)",
                "relyingPartyId": client_id,
                "logoUri": "https://openid.net/wp-content/uploads/2023/09/logo-c3f2e0c8.png",
                "redirectUris": list(redirect_uris),
                "publicKey": public_jwk,
                "authContextRefs": list(acrs),
                "userClaims": ["name", "email", "picture", "gender", "birthdate"],
                "grantTypes": ["authorization_code"],
                "clientAuthMethods": ["private_key_jwt"],
            },
        }
        url = f"{self.base}/client-mgmt/oidc-client"
        r = self.s.request(method, url, json=body, timeout=30)
        print(f"[esignet] register_client({method}) -> {r.status_code}: {r.text[:400]}")
        return r

    def begin_authorize(self, params: dict):
        """GET /oauth2/authorize without following redirects.
        Returns (auth_id, execution_id, location)."""
        r = self.s.get(f"{self.base}/oauth2/authorize", params=params,
                       allow_redirects=False, timeout=30)
        loc = r.headers.get("Location", "")
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(loc).query)
        auth_id = (q.get("authId") or [None])[0]
        execution_id = (q.get("executionId") or [None])[0]
        print(f"[esignet] authorize -> {r.status_code}, authId={auth_id}, executionId={execution_id}")
        if r.status_code not in (301, 302, 303) or not auth_id:
            print(f"[esignet] authorize unexpected response: {r.text[:600]}")
        return auth_id, execution_id, loc

    def flow_execute(self, body: dict) -> dict:
        r = self.s.post(f"{self.base}/flow/execute", json=body, timeout=30)
        try:
            out = r.json()
        except Exception:
            out = {"_status": r.status_code, "_text": r.text[:600]}
        print(f"[esignet] flow/execute {json.dumps(body)[:160]} -> {json.dumps(out)[:400]}")
        return out

    def drive_flow(self, execution_id: str, individual_id: str,
                   pin: str = "545411", otp: str = "111111",
                   captcha_token: str = "test-captcha-token", max_steps: int = 12) -> str:
        """Walk /flow/execute steps until COMPLETE; return the signed assertion."""
        resp = self.flow_execute({"executionId": execution_id})
        for _ in range(max_steps):
            status = (resp.get("flowStatus") or "").upper()
            if status == "COMPLETE":
                assertion = resp.get("assertion") or json.dumps(resp.get("data", {}))
                if isinstance(assertion, str) and assertion.count(".") == 2:
                    return assertion
                # some versions nest it
                return (resp.get("data") or {}).get("assertion") or assertion
            if status == "ERROR":
                raise RuntimeError(f"flow entered ERROR: {json.dumps(resp)[:600]}")

            challenge = resp.get("challengeToken")
            step = resp.get("step") or {}
            actions = step.get("actions") or []
            action_ids = [a.get("id", "") for a in actions] or [step.get("action", "")]
            inputs_meta = {i.get("id"): i for i in (step.get("inputs") or [])}
            print(f"[esignet] step actions={action_ids} inputs={list(inputs_meta)}")

            aid = action_ids[0] if action_ids else ""
            low = aid.lower()
            if "acr" in low:
                # choose the first offered authentication method
                choice = (step.get("options") or [{}])[0].get("id") or aid
                resp = self.flow_execute({"executionId": execution_id,
                                          "challengeToken": challenge, "action": aid,
                                          "inputs": {"acr": choice}})
            elif "uin" in low or "username" in low or "individual" in low or "login" in low:
                resp = self.flow_execute({"executionId": execution_id,
                                          "challengeToken": challenge, "action": aid,
                                          "inputs": {"username": individual_id,
                                                     "captcha_token": captcha_token}})
            elif "otp" in low:
                key = "otp" if "otp" in inputs_meta or not inputs_meta else list(inputs_meta)[0]
                resp = self.flow_execute({"executionId": execution_id,
                                          "challengeToken": challenge, "action": aid,
                                          "inputs": {key: otp}})
            elif "pin" in low or "password" in low or "knowledge" in low:
                key = "password" if "password" in inputs_meta else (list(inputs_meta)[0] if inputs_meta else "password")
                resp = self.flow_execute({"executionId": execution_id,
                                          "challengeToken": challenge, "action": aid,
                                          "inputs": {key: pin}})
            elif "consent" in low or "agree" in low or "confirm" in low:
                resp = self.flow_execute({"executionId": execution_id,
                                          "challengeToken": challenge, "action": aid,
                                          "inputs": {}})
            else:
                raise RuntimeError(f"unknown flow step actions={action_ids} step={json.dumps(step)[:600]}")
        raise RuntimeError("flow did not reach COMPLETE within step budget")

    def auth_callback(self, auth_id: str, assertion: str) -> str:
        r = self.s.post(f"{self.base}/oauth2/auth/callback",
                        json={"authId": auth_id, "assertion": assertion}, timeout=30)
        print(f"[esignet] auth/callback -> {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
        data = r.json()
        return data.get("redirect_uri") or data.get("redirectUri")

    def exchange_code(self, code: str, client_id: str, private_pem: str, redirect_uri: str) -> dict:
        token_url = f"{self.base}/oauth2/token"
        r = self.s.post(token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion(private_pem, client_id, token_url),
        }, timeout=30)
        print(f"[esignet] token -> {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
        return r.json()

    def authorization_code_flow(self, client_id: str, redirect_uri: str,
                                scope: str = "openid", individual_id: str = "1774231323",
                                extra_params: dict = None) -> dict:
        """Full scripted auth-code flow; returns the token endpoint response."""
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": "e2e-" + uuid.uuid4().hex[:12],
            "nonce": uuid.uuid4().hex,
        }
        if extra_params:
            params.update(extra_params)
        auth_id, execution_id, _ = self.begin_authorize(params)
        assertion = self.drive_flow(execution_id, individual_id)
        redirect = self.auth_callback(auth_id, assertion)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(redirect).query)
        code = q["code"][0]
        return redirect, code
