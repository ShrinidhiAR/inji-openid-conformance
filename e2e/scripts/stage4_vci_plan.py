#!/usr/bin/env python3
"""Stage 4: run the REAL OpenID Foundation conformance suite's
oid4vci-1_0-issuer-test-plan against the local inji-certify (mock-mdl profile,
mso_mdoc format - the only MOSIP credential format the suite's issuer plan
supports) with local eSignet 1.8.0 (Java, classic REST) as the authorization
server.

This is not a fixture and not a replay: the suite container executes its own
test modules against the running certify container. This script only plays the
role of the human wallet user. Suite VCI modules push their authorization
request to eSignet's PAR endpoint themselves (they hold the client's private
key); when a module parks in WAITING with a browser URL
(authorize?client_id=...&request_uri=...), this driver:

  1. resolves the pushed request via POST /authorization/par-oauth-details
     (single-use: eSignet evicts the request_uri on this call);
  2. verifies FAIL-CLOSED that the resolved credential scopes are exactly the
     credential scope advertised by the live issuer metadata (deployed-version
     computed value, acr null/empty - no openid scope, which eSignet 1.8.0's
     OIDCScopeValidator forbids alongside a credential scope);
  3. runs the classic authenticate (PWD, mock individual) and auth-code calls;
  4. hands the authorization code back to the suite by following its callback
     URL and replaying the suite's implicit-submit browser step (verified
     against a real captured suite page in the earlier eSignet-module stage).

Variant choice: openid=plain_oauth. The suite's own variant doc says "If your
server supports issuing id_tokens, pick 'openid connect'. Otherwise pick
plain_oauth." eSignet 1.8.0 issues no id_token for credential-scope flows
(credential scope may not be combined with openid), so plain_oauth is the
official variant matching the actual claimed test scope - no id_token or
protocol check is weakened; the suite still runs every VCI check of the
selected modules.

Outputs /tmp/stage4-vci-results.json with plan/test IDs and per-module
status/result, plus /tmp/stage4-suite-log-<module>.json with each non-PASSED
module's FULL event log (JWT bodies redacted) so suite failure args and the
resulting module state are preserved verbatim. Test failures are FINDINGS
about interop, not infra failures: the script exits 0 unless the harness
itself broke (HARNESS_* -> exit 2).
"""
import json
import os
import re
import sys
import time
import urllib.parse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esignet import gen_client_key
from esignet_classic import EsignetClassic, redact

SUITE = "http://localhost:8080"
ESIGNET_HOST = "http://localhost:8090"   # host-published gateway port
ESIGNET_ISSUER = "http://esignet:8088"   # in-network issuer string
CERTIFY = "http://localhost:8088"
# The suite rejects plain-HTTP requests unless this header marks them as
# arriving via a TLS-terminating proxy (discovered in stage 1).
SUITE_HDRS = {"X-Forwarded-Proto": "https"}
ALIAS = "inji-vci"
CALLBACK = f"http://localhost:8080/test/a/{ALIAS}/callback"
INDIVIDUAL = "1774231323"  # mock-identity-system seed (verified in stage 2)

VARIANT = {
    "fapi_profile": "vci",
    "credential_format": "mdoc",
    "authorization_request_type": "simple",
    "client_auth_type": "private_key_jwt",
    "fapi_request_method": "unsigned",
    "fapi_response_mode": "plain_response",
    "grant_management": "disabled",
    # plain_oauth: eSignet 1.8.0 issues no id_token for credential-scope
    # flows; see module docstring. Matches the claimed test scope.
    "openid": "plain_oauth",
    # eSignet 1.8.0 supports DPoP (DpopValidationFilter) but not mTLS client
    # auth, so dpop is the only sender-constrain option.
    "sender_constrain": "dpop",
    "vci_authorization_code_flow_variant": "wallet_initiated",
    "vci_credential_encryption": "plain",
    "vci_grant_type": "authorization_code",
}

RESULTS_FILE = os.environ.get("RESULTS_FILE", "/tmp/stage4-vci-results.json")
CALLBACK_HTML_FILE = os.environ.get("CALLBACK_HTML_FILE", "/tmp/suite-callback-page.html")
LOG_DIR = os.environ.get("SUITE_LOG_DIR", "/tmp")


def suite(method: str, path: str, **kw) -> requests.Response:
    kw.setdefault("headers", {}).update(SUITE_HDRS)
    kw.setdefault("timeout", 45)
    # the suite's long-poll endpoints occasionally drop connections; retry
    # transport errors instead of crashing the whole plan run
    for attempt in range(4):
        try:
            return requests.request(method, SUITE + path, **kw)
        except requests.ConnectionError as e:
            if attempt == 3:
                raise
            print(f"[suite] {method} {path} connection error ({e.__class__.__name__}); retrying")
            time.sleep(3)


class HarnessReplayError(RuntimeError):
    """The driver failed to replay a suite browser step - harness, not product."""


def replay_implicit_submit(callback_url: str, html: str):
    """The suite answers the auth-code callback with its implicitCallback page:
    browser JS is expected to POST window.location.hash (empty for query-mode
    responses) back to a random /implicit/{id} URL
    (AbstractRedirectServerTestModule). No JS runs here, so replay that step or
    the module waits forever. Verified against a real captured suite page
    (stage 1); fails closed when the page is not what we expect."""
    with open(CALLBACK_HTML_FILE, "w") as fh:
        fh.write(html)
    print(f"[suite-browser] callback page saved ({len(html)} bytes) -> {CALLBACK_HTML_FILE}")
    # thymeleaf javascript-inlines the URL as a double-quoted JS string literal;
    # accept either quote style
    m = re.search("xhr\\.open\\('POST',\\s*['\"]([^'\"]+)", html)
    if not m:
        raise HarnessReplayError(
            "no implicit-submit URL parsed from the rendered callback page "
            f"(saved to {CALLBACK_HTML_FILE}) - aborting promptly instead of "
            "letting the module park")
    raw_submit = m.group(1)
    # thymeleaf's javascript serializer escapes '/' as '\/' inside the string
    # literal (observed in the real rendered page); undo JS string escaping
    try:
        raw_submit = json.loads('"' + raw_submit.replace('"', '') + '"')
    except ValueError:
        raw_submit = raw_submit.replace("\\/", "/")
    # the submit target must belong to this suite instance's implicit path:
    # {suite-origin}/test/a/{alias}/implicit/{id}; anything else means the
    # callback page is not what we expect - abort
    expect = urllib.parse.urlsplit(SUITE)
    got = urllib.parse.urlsplit(raw_submit)
    if (got.scheme, got.hostname, got.port) != (expect.scheme, expect.hostname, expect.port) \
            or not got.path.startswith(f"/test/a/{ALIAS}/implicit/"):
        raise HarnessReplayError(f"unexpected implicit-submit target {raw_submit!r}")
    fragment = urllib.parse.urlsplit(callback_url).fragment
    rs = requests.post(urllib.parse.urlunsplit(got), data=fragment,
                       headers={**SUITE_HDRS, "Content-Type": "text/plain"},
                       timeout=45)
    print(f"[suite-browser] implicit submit ({got.path.rsplit('/',1)[-1]}) -> {rs.status_code} {rs.text[:150]}")
    if not 200 <= rs.status_code < 300:
        raise HarnessReplayError(f"suite rejected implicit submit: {rs.status_code} {rs.text[:200]}")


def drive_authorize_url(es: EsignetClassic, url: str, expected_scope: str):
    """Play the wallet user for one suite-provided authorize URL.

    The suite built this URL from the AS metadata's authorization_endpoint
    with exactly client_id + request_uri (FAPI2 PAR redirect,
    BuildRequestObjectByReferenceRedirectToAuthorizationEndpointWithout
    Duplicates). Anything else means the flow is not what this driver
    implements - fail closed."""
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    client_id = q.get("client_id")
    request_uri = q.get("request_uri")
    if not client_id or not request_uri:
        raise HarnessReplayError(
            f"suite browser URL is not a PAR redirect (params: {sorted(q)}) - "
            "this driver only implements the PAR wallet-user step")
    unexpected = set(q) - {"client_id", "request_uri"}
    if unexpected:
        raise HarnessReplayError(f"unexpected params on PAR redirect URL: {sorted(unexpected)}")
    print(f"[suite-browser] PAR redirect: client_id={client_id} request_uri={request_uri[:60]}...")

    details = es.par_oauth_details(client_id, request_uri)
    # Fail-closed scope check: the resolved credential scopes must be exactly
    # the credential scope the DEPLOYED issuer metadata advertises (suite set
    # client.scope from it verbatim per
    # VCIDetermineCredentialConfigurationTransferMethod), with no openid
    # scope - eSignet 1.8.0 forbids mixing them (OIDCScopeValidator). acr
    # stays null/empty: the suite's PAR body carries no acr_values and this
    # driver adds none.
    cred_scopes = details.get("credentialScopes") or []
    authz_scopes = details.get("authorizeScopes") or []
    if cred_scopes != [expected_scope] or "openid" in authz_scopes:
        raise HarnessReplayError(
            f"resolved scopes do not match the deployed credential scope: "
            f"credentialScopes={cred_scopes} authorizeScopes={authz_scopes} "
            f"expected exactly [{expected_scope!r}] and no openid")
    print(f"[suite-browser] resolved credential scope OK: {cred_scopes}")

    tid = details["transactionId"]
    es.authenticate(tid, INDIVIDUAL)
    claims = list(dict.fromkeys(
        (details.get("essentialClaims") or []) + (details.get("voluntaryClaims") or [])))
    ac = es.auth_code(tid, claims, authz_scopes)
    redirect = ac.get("redirectUri")
    state = ac.get("state")
    code = ac.get("code")
    if not redirect or state is None or not code:
        raise HarnessReplayError(
            f"auth-code response incomplete (redirectUri={'set' if redirect else 'MISSING'} "
            f"state={'set' if state is not None else 'MISSING'} code={'set' if code else 'MISSING'})")
    sep = "&" if "?" in redirect else "?"
    callback_url = (f"{redirect}{sep}code={urllib.parse.quote(code, safe='')}"
                    f"&state={urllib.parse.quote(state, safe='')}")
    # following the callback hands the code to the suite's redirect endpoint
    r = requests.get(callback_url, headers=SUITE_HDRS, allow_redirects=False, timeout=45)
    print(f"[suite-browser] callback -> {r.status_code} location={r.headers.get('Location','')[:200]}")
    replay_implicit_submit(callback_url, r.text)


# --- artifact scrubber -------------------------------------------------------
# Redact BEFORE serialization - redacting the serialized form injects
# unescaped quotes and corrupts the JSON (observed on run 40543683358).
# The suite logs its config verbatim, including client.jwks PRIVATE keys
# (observed exposed on run 40543683358 -> artifact deleted, containment).
_JWK_PRIVATE_MEMBERS = {"d", "k", "p", "q", "dp", "dq", "qi", "oth"}
_PEM_PRIVATE_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----[^-]*-----END (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----",
    re.DOTALL,
)


def _redact_for_artifact(o):
    """Recursively scrub secrets from suite log entries before json.dump.

    - strings: compact JWTs via redact(), PEM private-key blocks
    - dicts that look like JWKs (carry "kty"): private members replaced;
      public members (kty/crv/x/y/kid/use/alg) preserved
    - dicts without "kty": recursed untouched - a bare "d" key elsewhere is
      harmless data, not key material, and must not be stripped blindly
    """
    if isinstance(o, str):
        return _PEM_PRIVATE_RE.sub("<PEM private key redacted>", redact(o))
    if isinstance(o, list):
        return [_redact_for_artifact(v) for v in o]
    if isinstance(o, dict):
        if "kty" in o:
            return {k: ("<redacted private jwk member>" if k in _JWK_PRIVATE_MEMBERS
                        else _redact_for_artifact(v)) for k, v in o.items()}
        return {k: _redact_for_artifact(v) for k, v in o.items()}
    return o


def main() -> int:
    from mdl_config import ensure_mdl_config
    mdoc_id, issuer_url = ensure_mdl_config(CERTIFY)
    print(f"[plan] issuer={issuer_url} credential_configuration_id={mdoc_id}")

    # the credential scope the suite will adopt from the live issuer metadata
    md = requests.get(f"{CERTIFY}/v1/certify/.well-known/openid-credential-issuer",
                      timeout=30).json()
    expected_scope = md["credential_configurations_supported"][mdoc_id]["scope"]
    print(f"[plan] deployed credential scope (from live metadata): {expected_scope}")

    pem_path = "e2e/compose/certify/config/mdl-issuer-trust-anchor.pem"
    trust_anchor_pem = open(pem_path).read()

    _, pub1, priv1 = gen_client_key(); pub1["kid"] = priv1["kid"] = "suite-vci-1"
    _, pub2, priv2 = gen_client_key(); pub2["kid"] = priv2["kid"] = "suite-vci-2"

    es = EsignetClassic(ESIGNET_HOST, ESIGNET_ISSUER)
    for cid, pub in (("inji-vci-suite", pub1), ("inji-vci-suite-2", pub2)):
        r = es.register_client(cid, [CALLBACK], pub)
        if r.status_code not in (200, 201):
            print(f"[plan] create failed for {cid}, trying update (PUT)")
            r = es.register_client(cid, [CALLBACK], pub, method="PUT")
        body = {}
        try:
            body = r.json()
        except Exception:
            pass
        if r.status_code not in (200, 201) or body.get("errors"):
            print(f"::error::could not register suite client {cid} at eSignet: "
                  f"{r.status_code} {redact(r.text)[:300]}")
            return 1

    config = {
        "alias": ALIAS,
        "description": "OID4VCI 1.0 issuer plan vs local inji-certify mock-mdl + local eSignet 1.8.0 classic (e2e harness)",
        "vci": {
            "credential_issuer_url": issuer_url,
            "authorization_server": ESIGNET_ISSUER,
            "credential_configuration_id": mdoc_id,
            "credential_proof_type_hint": "jwt",
        },
        "credential": {"trust_anchor_pem": trust_anchor_pem},
        # client.scope is REPLACED by the suite from the issuer metadata's
        # credential configuration scope
        # (VCIDetermineCredentialConfigurationTransferMethod); the value here
        # is a placeholder only.
        "client": {"client_id": "inji-vci-suite", "scope": "openid", "jwks": {"keys": [priv1]}},
        "client2": {"client_id": "inji-vci-suite-2", "scope": "openid", "jwks": {"keys": [priv2]}},
    }
    r = suite("POST", "/api/plan",
              params={"planName": "oid4vci-1_0-issuer-test-plan", "variant": json.dumps(VARIANT)},
              data=json.dumps(config),
              headers={"Content-Type": "application/json"})
    print(f"[plan] create -> {r.status_code}: {r.text[:400]}")
    if r.status_code != 201:
        print("::error::suite rejected the test plan config")
        return 1
    plan = r.json()
    plan_id = plan.get("id") or plan.get("planId")
    print(f"[plan] created plan id={plan_id}")

    module_names = []
    for m in plan.get("modules", []):
        name = m.get("testModule") or m.get("moduleName") or m.get("name")
        if name:
            module_names.append(name)
    if not module_names:
        print(f"::error::plan response carried no module names: {json.dumps(plan)[:600]}")
        return 1
    print(f"[plan] {len(module_names)} modules in plan")
    # bounded scope: run only selected modules (comma-separated exact names);
    # default establishes the happy path first.
    sel = os.environ.get("MODULES",
        "oid4vci-1_0-issuer-happy-flow")
    wanted = [w.strip() for w in sel.split(",") if w.strip()]
    module_names = [m for m in module_names if m in wanted]
    print(f"[plan] running {len(module_names)} selected modules: {module_names}")

    results = []
    def flush():
        with open(RESULTS_FILE, "w") as fh:
            json.dump({"plan_id": plan_id, "results": results}, fh, indent=2)

    for name in module_names:
        print(f"\n[module] === {name} ===")
        r = suite("POST", "/api/runner", params={"test": name, "plan": plan_id})
        if r.status_code != 201:
            print(f"[module] create failed: {r.status_code} {r.text[:300]}")
            results.append({"module": name, "status": "HARNESS_ERROR", "result": None})
            continue
        mid = r.json().get("id")
        # start = POST /api/runner/{id} (TestRunner.java @PostMapping("/runner/{id}"))
        r = suite("POST", f"/api/runner/{mid}")
        print(f"[module] started id={mid} -> {r.status_code}: {r.text[:300]}")

        status = result = None
        driven = set()  # PAR request_uris are single-use; drive each URL once
        deadline = time.time() + 300
        while time.time() < deadline:
            try:
                w = suite("GET", f"/api/runner/{mid}/wait-state",
                          params={"states": "WAITING,FINISHED,INTERRUPTED", "timeoutMs": "30000"}).json()
            except Exception as e:
                print(f"[module] wait-state error: {e}; retrying")
                time.sleep(5)
                continue
            state = w.get("state") or w.get("status")
            if w.get("timeout") or not state:
                info = suite("GET", f"/api/info/{mid}").json()
                state = info.get("status")
                if state not in ("WAITING", "FINISHED", "INTERRUPTED"):
                    continue
            if state == "WAITING":
                try:
                    b = suite("GET", f"/api/runner/browser/{mid}").json()
                except Exception as e:
                    print(f"[module] browser-url fetch failed: {e}; retrying")
                    time.sleep(5)
                    continue
                urls = [u for u in (b.get("urls") or []) if u not in driven]
                if not urls:
                    continue
                url = urls[0]
                driven.add(url)
                try:
                    drive_authorize_url(es, url, expected_scope)
                except HarnessReplayError as e:
                    # driver defect, not a product verdict: record distinctly
                    # and stop promptly instead of waiting out the deadline
                    print(f"[module] HARNESS REPLAY FAILURE: {e}")
                    status, result = "HARNESS_INCOMPLETE", None
                    break
                except Exception as e:
                    print(f"[module] browser drive failed: {e}")
                    # the suite decides what a dead front-channel means
                    time.sleep(5)
                continue
            info = suite("GET", f"/api/info/{mid}").json()
            status = info.get("status")
            result = info.get("result")
            break
        else:
            # deadline expired with no terminal state: harness-incomplete,
            # never to be read as a product outcome
            print(f"[module] deadline expired without terminal state for {name}")
            status, result = "HARNESS_TIMEOUT", None

        # preserve the module's FULL event log (JWT bodies redacted) as its own
        # artifact: suite failure args and resulting module state stay
        # available verbatim instead of only as an excerpt
        error_excerpt = None
        log_file = None
        try:
            entries = suite("GET", f"/api/log/{mid}").json()
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
            log_file = os.path.join(LOG_DIR, f"stage4-suite-log-{safe}.json")
            with open(log_file, "w") as fh:
                json.dump(_redact_for_artifact(entries), fh, indent=2, default=str)
            print(f"[module] full event log saved ({len(entries) if isinstance(entries, list) else '?'} entries) -> {log_file}")
            if result != "PASSED":
                for e in entries if isinstance(entries, list) else []:
                    msg = e.get("msg") if isinstance(e, dict) else str(e)
                    src = e.get("source") if isinstance(e, dict) else ""
                    print(f"   [{src}] {str(msg)[:200]}")
                bad = []
                for e in entries if isinstance(entries, list) else []:
                    msg = json.dumps(e)
                    if any(k in msg.lower() for k in ("error", "exception", "fail", "invalid")):
                        bad.append(e.get("msg") if isinstance(e, dict) else msg)
                error_excerpt = [redact(str(b))[:400] for b in (bad[:4] or [])] or None
                print(f"[module] log excerpt: {json.dumps(error_excerpt)[:800]}")
        except Exception as e:
            print(f"[module] could not fetch log: {e}")
        print(f"[module] {name}: status={status} result={result}")
        results.append({"module": name, "test_id": mid, "status": status,
                        "result": result, "error_excerpt": error_excerpt,
                        "event_log_file": os.path.basename(log_file) if log_file else None})
        flush()  # preserve partial evidence if the job is cancelled later

    counts = {}
    for r0 in results:
        key = r0["result"] or r0["status"] or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    out = {
        "plan": "oid4vci-1_0-issuer-test-plan",
        "plan_id": plan_id,
        "variant": VARIANT,
        "issuer": issuer_url,
        "credential_configuration_id": mdoc_id,
        "counts": counts,
        "results": results,
        "note": "Real OIDF conformance suite executing against local inji-certify "
                "(mock-mdl) + local eSignet 1.8.0 classic. Non-PASSED results are "
                "interop findings, recorded verbatim, not harness failures.",
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[summary] {json.dumps(counts)}")
    harness_bad = [r0 for r0 in results
                   if r0["status"] in ("HARNESS_INCOMPLETE", "HARNESS_TIMEOUT", "HARNESS_ERROR")]
    for r0 in results:
        if r0["status"] in ("HARNESS_INCOMPLETE", "HARNESS_TIMEOUT", "HARNESS_ERROR"):
            print(f"::error::harness-incomplete: {r0['module']}: {r0['status']}")
        elif r0["result"] != "PASSED":
            print(f"::warning::{r0['module']}: {r0['status']}/{r0['result']}")
    if harness_bad:
        print(f"[summary] {len(harness_bad)} module(s) harness-incomplete; exiting nonzero "
              "so green never masks an incomplete run")
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
