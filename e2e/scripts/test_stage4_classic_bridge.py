#!/usr/bin/env python3
"""Bounded local harness test for the stage4 classic PAR bridge
(stage4_vci_plan.drive_authorize_url): sign-in (classic par-oauth-details ->
authenticate -> auth-code), fixture bootstrap, and the suite callback +
implicit-submit replay - against stub servers that validate every request
shape. The suite itself (PAR POST, token exchange, credential issuance) is
not runnable locally; those legs are covered by the live run only.

Also writes the stage4 bootstrap fixtures to e2e/fixtures/stage4/:
SYNTHETIC, single-capture shapes that document the interface this driver
implements. They are NOT evidence of protocol conformance.

Run: python e2e/scripts/test_stage4_classic_bridge.py  (no external services)
"""
import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "e2e/scripts")
import stage4_vci_plan
from esignet_classic import EsignetClassic

ESIGNET_BASE = "http://127.0.0.1:18124"
SUITE_BASE = "http://127.0.0.1:18125"
ALIAS = "inji-vci"
CALLBACK_PATH = f"/test/a/{ALIAS}/callback"
IMPLICIT_ID = "xyz123implicit"
ISSUER = "http://esignet:8088"
CLIENT_ID = "inji-vci-suite"
REQUEST_URI = "urn:ietf:params:oauth:request_uri:AbCdEf123singleUse"
SCOPE = "sample_vc_mdoc"
FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "stage4")

seen = {"callback_query": None, "implicit_body": None, "implicit_path": None}

# the synthetic suite browser URL: exactly client_id + request_uri, matching
# BuildRequestObjectByReferenceRedirectToAuthorizationEndpointWithoutDuplicates
SUITE_AUTHORIZE_URL = (f"{ISSUER}/authorize?client_id={CLIENT_ID}"
                       f"&request_uri={urllib.parse.quote(REQUEST_URI, safe='')}")

# the implicit-submit page: mirrors the real thymeleaf-rendered suite page
# captured in stage 1 (double-quoted JS string, '/' escaped as '\/')
IMPLICIT_URL = f"{SUITE_BASE}/test/a/{ALIAS}/implicit/{IMPLICIT_ID}"
IMPLICIT_PAGE = (
    "<html><head><script>\n"
    "function f() {\n"
    f"  xhr.open('POST', \"{IMPLICIT_URL.replace('/', chr(92) + '/')}\", true);\n"
    "  xhr.send(window.location.hash ? window.location.hash.substring(1) : '');\n"
    "}\n"
    "</script></head><body onload='f()'></body></html>"
)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


class EsignetStub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_csrf(self):
        import base64 as b64
        raw = b"csrf-123"
        h = self.headers.get("X-XSRF-TOKEN", "")
        ok = False
        try:
            b = b64.urlsafe_b64decode(h)
            ok = len(b) == 2 * len(raw) and \
                bytes(x ^ y for x, y in zip(b[:len(raw)], b[len(raw):])) == raw
        except Exception:
            ok = False
        check(ok, f"missing/wrong XOR-masked X-XSRF-TOKEN on POST {self.path}")

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers["Content-Length"])))

    def do_GET(self):
        if self.path == "/v1/esignet/csrf/token":
            self.send_response(200)
            body = json.dumps({"token": "csrf-123"}).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", "XSRF-TOKEN=csrf-123; Path=/")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"errors": [{"errorCode": "unknown_path"}]}, 404)

    def do_POST(self):
        self._check_csrf()
        env = self._body()
        req = env.get("request", {})
        if self.path == "/v1/esignet/authorization/par-oauth-details":
            # PushedOAuthDetailRequest: clientId + requestUri ONLY - no scope,
            # no acr_values (the PAR body carries them; acr null/empty)
            check(set(req) == {"clientId", "requestUri"},
                  f"par-oauth-details must carry only clientId+requestUri, got {sorted(req)}")
            check(req["clientId"] == CLIENT_ID, "clientId mismatch")
            check(req["requestUri"] == REQUEST_URI, "requestUri mismatch")
            resp = {"transactionId": "tx-par-1",
                    "credentialScopes": [SCOPE],
                    "authorizeScopes": [SCOPE],
                    "essentialClaims": ["given_name"],
                    "voluntaryClaims": ["family_name"],
                    "authFactors": [{"type": "PWD", "format": "alpha-numeric"}]}
            self._json({"responseTime": "2026-10-27T00:00:00.000Z", "response": resp})
        elif self.path == "/v1/esignet/authorization/authenticate":
            check(self.headers.get("oauth-details-key") == "tx-par-1", "missing oauth-details-key")
            import base64 as b64, hashlib
            expected = b64.urlsafe_b64encode(hashlib.sha256(json.dumps(
                {"transactionId": "tx-par-1", "credentialScopes": [SCOPE],
                 "authorizeScopes": [SCOPE], "essentialClaims": ["given_name"],
                 "voluntaryClaims": ["family_name"],
                 "authFactors": [{"type": "PWD", "format": "alpha-numeric"}]},
                separators=(",", ":")).encode()).digest()).decode().rstrip("=")
            check(self.headers.get("oauth-details-hash") == expected, "wrong oauth-details-hash")
            self._json({"responseTime": "2026-10-27T00:00:01.000Z", "response": {"transactionId": "tx-par-1"}})
        elif self.path == "/v1/esignet/authorization/auth-code":
            check(self.headers.get("oauth-details-key") == "tx-par-1", "missing oauth-details-key")
            check(req["permittedAuthorizeScopes"] == [SCOPE], "permitted scopes must be credential scope only")
            self._json({"responseTime": "2026-10-27T00:00:02.000Z", "response": {
                "transactionId": "tx-par-1",
                "code": "stub-auth-code-7f3a",
                "state": "suite-state-9z",
                "redirectUri": SUITE_BASE + CALLBACK_PATH}})
        else:
            self._json({"errors": [{"errorCode": "unknown_path"}]}, 404)


class SuiteStub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith(CALLBACK_PATH):
            seen["callback_query"] = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            body = IMPLICIT_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path.startswith(f"/test/a/{ALIAS}/implicit/"):
            seen["implicit_path"] = self.path
            seen["implicit_body"] = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
            body = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()


def run_servers():
    e = HTTPServer(("127.0.0.1", 18124), EsignetStub)
    s = HTTPServer(("127.0.0.1", 18125), SuiteStub)
    threading.Thread(target=e.serve_forever, daemon=True).start()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return e, s


def write_fixtures(callback_url):
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    with open(os.path.join(FIXTURE_DIR, "suite-authorize-url.txt"), "w") as fh:
        fh.write("# SYNTHETIC, single-capture interface shape - NOT conformance evidence.\n"
                 "# Query params exactly as the suite builds them for a FAPI2 PAR redirect\n"
                 "# (BuildRequestObjectByReferenceRedirectToAuthorizationEndpointWithoutDuplicates):\n"
                 "# client_id + request_uri only.\n"
                 + SUITE_AUTHORIZE_URL + "\n")
    with open(os.path.join(FIXTURE_DIR, "authorize-callback.txt"), "w") as fh:
        fh.write("# SYNTHETIC, single-capture interface shape - NOT conformance evidence.\n"
                 "# Callback the driver builds from the classic auth-code response and GETs\n"
                 "# against the suite's redirect endpoint (code/state values are stub values).\n"
                 + callback_url + "\n")
    with open(os.path.join(FIXTURE_DIR, "implicit-submit-page.html"), "w") as fh:
        fh.write("<!-- SYNTHETIC reproduction, single capture - NOT conformance evidence.\n"
                 "     Mirrors the real thymeleaf-rendered suite implicitCallback page captured\n"
                 "     in stage 1 (double-quoted JS string literal, '/' escaped as '\\/'). -->\n"
                 + IMPLICIT_PAGE + "\n")


def main():
    e, s = run_servers()
    # point the stage4 module at the stubs
    stage4_vci_plan.SUITE = SUITE_BASE
    stage4_vci_plan.CALLBACK_HTML_FILE = "/tmp/test-suite-callback-page.html"

    es = EsignetClassic(ESIGNET_BASE, ISSUER)
    captured = {}
    real_get = stage4_vci_plan.requests.get
    def spy_get(url, **kw):
        captured["callback_url"] = url
        return real_get(url, **kw)
    stage4_vci_plan.requests.get = spy_get
    try:
        stage4_vci_plan.drive_authorize_url(es, SUITE_AUTHORIZE_URL, SCOPE)
    finally:
        stage4_vci_plan.requests.get = real_get

    check(seen["callback_query"] and seen["callback_query"].get("code") == "stub-auth-code-7f3a",
          f"suite callback did not receive the code: {seen['callback_query']}")
    check(seen["callback_query"].get("state") == "suite-state-9z",
          f"suite callback did not receive the state: {seen['callback_query']}")
    check(seen["implicit_path"] == f"/test/a/{ALIAS}/implicit/{IMPLICIT_ID}",
          f"implicit POST hit wrong path: {seen['implicit_path']}")
    check(seen["implicit_body"] == "", f"implicit POST body should be empty (query mode): {seen['implicit_body']!r}")
    print("PASS happy path: sign-in -> auth code -> suite callback -> implicit submit replay")

    # negative: no request_uri on the browser URL
    try:
        stage4_vci_plan.drive_authorize_url(es, f"{ISSUER}/authorize?client_id={CLIENT_ID}&scope=x", SCOPE)
        check(False, "expected HarnessReplayError for non-PAR URL")
    except stage4_vci_plan.HarnessReplayError as ex:
        check("not a PAR redirect" in str(ex), str(ex))
    print("PASS fail-closed: browser URL without request_uri rejected")

    # negative: unexpected duplicate params on the PAR redirect
    try:
        stage4_vci_plan.drive_authorize_url(es, SUITE_AUTHORIZE_URL + "&scope=openid", SCOPE)
        check(False, "expected HarnessReplayError for duplicate params")
    except stage4_vci_plan.HarnessReplayError as ex:
        check("unexpected params" in str(ex), str(ex))
    print("PASS fail-closed: unexpected params on PAR redirect rejected")

    # negative: resolved scopes must match the deployed credential scope exactly
    try:
        stage4_vci_plan.drive_authorize_url(es, SUITE_AUTHORIZE_URL, "some_other_scope")
        check(False, "expected HarnessReplayError for scope mismatch")
    except stage4_vci_plan.HarnessReplayError as ex:
        check("resolved scopes do not match" in str(ex), str(ex))
    print("PASS fail-closed: resolved scope != deployed credential scope rejected")

    # negative: callback page without the implicit-submit URL aborts promptly
    class BadPage(SuiteStub):
        def do_GET(self):
            body = b"<html>no js here</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    bad = HTTPServer(("127.0.0.1", 18126), BadPage)
    threading.Thread(target=bad.serve_forever, daemon=True).start()
    stage4_vci_plan.SUITE = "http://127.0.0.1:18126"
    try:
        stage4_vci_plan.replay_implicit_submit("http://x/cb", "<html>no js here</html>")
        check(False, "expected HarnessReplayError for missing implicit URL")
    except stage4_vci_plan.HarnessReplayError as ex:
        check("no implicit-submit URL" in str(ex), str(ex))
    finally:
        stage4_vci_plan.SUITE = SUITE_BASE
    print("PASS fail-closed: missing implicit-submit URL aborts (no parking)")

    write_fixtures(captured["callback_url"])
    print(f"PASS fixtures written -> {os.path.relpath(FIXTURE_DIR)} (synthetic, single-capture)")
    e.shutdown(); s.shutdown(); bad.shutdown()
    print("ALL STAGE4 BRIDGE CONTRACT TESTS PASSED")


if __name__ == "__main__":
    main()
