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


DEFAULT_KID = "e2e-key-1"


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
        "kid": DEFAULT_KID,
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
    der = key.sign(f"{h}.{p}".encode(), _ec.ECDSA(hashes.SHA256()))
    # JWS ES256 signature is raw R||S (2x32 bytes); cryptography returns DER.
    # Posting the DER blob makes eSignet reject the client assertion with
    # 401 invalid_client.
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    r, sv = decode_dss_signature(der)
    sig = r.to_bytes(32, "big") + sv.to_bytes(32, "big")
    return f"{h}.{p}.{_b64u(sig)}"


def client_assertion(private_pem: str, client_id: str, aud: str, kid: str = DEFAULT_KID) -> str:
    now = int(time.time())
    return _sign_es256(
        private_pem,
        {"alg": "ES256", "typ": "JWT", "kid": kid},
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
                        method: str = "POST",
                        additional_config: dict = None):
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
        # NOTE: the esignet 2.0.0 image's client-mgmt decoder rejects bodies with
        # unknown fields (invalid_input), so additionalConfig is only sent when the
        # caller provides one - and even then it may be rejected by the 2.0.0 image
        # (master supports it, 2.0.0 may predate it). DPoP binding is also automatic
        # per RFC 9449 when the client sends a DPoP proof, which is what the suite does.
        if additional_config:
            body["request"]["additionalConfig"] = additional_config
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

    @staticmethod
    def _norm(s: str) -> str:
        return "".join(c for c in s.lower() if c.isalnum())

    def drive_flow(self, execution_id: str, individual_id: str,
                   pin: str = "Mosip@123", otp: str = "111111",
                   captcha_token: str = "10000000-aaaa-bbbb-cccc-000000000001",
                   # default password verified against the mock-identity-system 0.14.0
                   # seed (init.sql: individual 1774231323 stores sha256("Mosip@123"));
                   # the PIN 545411 from older docs is a different field and fails
                   # the 2.0 password factor with FET-1005.
                   max_steps: int = 15) -> str:
        """Walk /flow/execute steps until COMPLETE; return the signed assertion.

        Mirrors mosip/esignet api-test internal/esignet/driver.go: actions come
        from data.actions[].ref, inputs from data.inputs[].identifier, the
        challengeToken is threaded through, and every step re-sends ALL inputs
        accumulated so far (browser behavior).
        """
        answers = {
            "username": individual_id, "individualid": individual_id,
            "uin": individual_id, "vid": individual_id,
            "password": pin, "pin": pin,
            "otp": otp, "otps": otp,
            "captcha": captcha_token, "captchatoken": captcha_token,
        }
        nav_hints = ("back", "cancel", "resend", "retry", "skip")
        payload = {"executionId": execution_id}
        carried = {}
        challenge = None
        for _ in range(max_steps):
            resp = self.flow_execute(payload)
            status = (resp.get("flowStatus") or "").upper()
            if resp.get("challengeToken"):
                challenge = resp["challengeToken"]
            if status == "COMPLETE":
                assertion = resp.get("assertion")
                if assertion:
                    return assertion
                raise RuntimeError(f"COMPLETE without assertion: {json.dumps(resp)[:500]}")
            if status and status != "INCOMPLETE":
                raise RuntimeError(f"flow terminated: {json.dumps(resp)[:600]}")
            if resp.get("error") and isinstance(resp["error"], dict) and resp["error"].get("code"):
                raise RuntimeError(f"flow step rejected: {json.dumps(resp['error'])[:400]}")

            data = resp.get("data") or {}
            actions = [a["ref"] for a in (data.get("actions") or []) if a.get("ref")]
            inputs = [i["identifier"] for i in (data.get("inputs") or []) if i.get("identifier")]
            candidates = [a for a in actions if not any(h in a.lower() for h in nav_hints)]
            if not candidates:
                raise RuntimeError(f"only nav actions available: {actions}")
            # prefer a deterministic credential path when offered a choice
            action = next((a for a in candidates if "password" in a.lower()
                           or "kbi" in a.lower()), candidates[0])
            print(f"[esignet] actions={actions} inputs={inputs} -> action={action}")

            for ident in inputs:
                v = answers.get(self._norm(ident))
                if v is None:
                    if "consent" in self._norm(ident):
                        v = json.dumps({"essential": True})
                    else:
                        raise RuntimeError(f"no answer for input '{identifier_hint}'" if False else f"no answer for input '{ident}' (inputs={inputs})")
                carried[ident] = v

            payload = {"executionId": execution_id}
            if challenge:
                payload["challengeToken"] = challenge
            payload["action"] = action
            if carried:
                payload["inputs"] = dict(carried)
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
        # private_key_jwt audience, confirmed by the stage2 probe matrix against the
        # real 2.0.0 image: the ISSUER URL (http://esignet:8080), not the token
        # endpoint path. kid must be present in the assertion header (registered
        # jwk carries kid=e2e-key-1). Token-URL aud and kid-less assertions both
        # get 401 invalid_client; issuer aud + kid returns 200.
        aud = "http://esignet:8080"
        r = self.s.post(token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion(private_pem, client_id, aud),
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
