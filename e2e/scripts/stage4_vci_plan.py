#!/usr/bin/env python3
"""Stage 4: run the REAL OpenID Foundation conformance suite's
oid4vci-1_0-issuer-test-plan against the local inji-certify (mock-mdl profile,
mso_mdoc format - the only MOSIP credential format the suite's issuer plan
supports) with local eSignet as the authorization server.

This is not a fixture and not a replay: the suite container executes its own
21 test modules against the running certify container. This script only plays
the role of the human wallet user: when a module parks in WAITING with a
browser URL (the eSignet authorize URL), it performs the scripted eSignet
login (same driver as stage 2/3) and follows the redirect back to the suite.

Outputs /tmp/stage4-vci-results.json with per-module status/result so the
workflow can upload it verbatim. Test failures are FINDINGS about interop,
not infra failures: the script exits 0 unless the harness itself broke.
"""
import json
import re
import os
import sys
import time
import urllib.parse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esignet import Esignet, gen_client_key

SUITE = "http://localhost:8080"
ESIGNET = "http://localhost:8090"
CERTIFY = "http://localhost:8088"
# The suite rejects plain-HTTP requests unless this header marks them as
# arriving via a TLS-terminating proxy (discovered in stage 1).
SUITE_HDRS = {"X-Forwarded-Proto": "https"}
ALIAS = "inji-vci"
CALLBACK = f"http://localhost:8080/test/a/{ALIAS}/callback"
INDIVIDUAL = "1774231323"  # mock-identity-system seed (verified in stage 2)
# browser URLs produced by the suite point at in-network service names; the
# script runs on the runner host, so rewrite to the published host ports.
HOST_REWRITE = {"esignet:8080": "localhost:8090", "certify:8090": "localhost:8088"}

VARIANT = {
    "fapi_profile": "vci",
    "credential_format": "mdoc",
    "authorization_request_type": "simple",
    "client_auth_type": "private_key_jwt",
    "fapi_request_method": "unsigned",
    "fapi_response_mode": "plain_response",
    "grant_management": "disabled",
    "openid": "openid_connect",
    # eSignet 2.0 supports DPoP but not mTLS client auth, so dpop is the only
    # sender-constrain option; the client is opted in via additionalConfig.
    "sender_constrain": "dpop",
    "vci_authorization_code_flow_variant": "wallet_initiated",
    "vci_credential_encryption": "plain",
    "vci_grant_type": "authorization_code",
}

def rewrite(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    netloc = parts.netloc
    if netloc in HOST_REWRITE:
        parts = parts._replace(netloc=HOST_REWRITE[netloc])
    return urllib.parse.urlunsplit(parts)

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


def drive_browser_url(es: Esignet, url: str):
    """Play the wallet user for one suite-provided authorize URL."""
    url = rewrite(url)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    print(f"[suite-browser] authorize URL params: client_id={q.get('client_id')} "
          f"redirect_uri={q.get('redirect_uri')} scope={q.get('scope')}")
    auth_id, execution_id, _ = es.begin_authorize(q)
    if not auth_id:
        raise RuntimeError("esignet authorize did not yield an authId")
    assertion = es.drive_flow(execution_id, INDIVIDUAL)
    redirect = es.auth_callback(auth_id, assertion)
    redirect = rewrite(redirect)
    # following the redirect hands the code to the suite's callback
    r = requests.get(redirect, headers=SUITE_HDRS, allow_redirects=False, timeout=45)
    print(f"[suite-browser] callback -> {r.status_code} location={r.headers.get('Location','')[:200]}")
    # always preserve the actual rendered callback page as artifact evidence
    with open(CALLBACK_HTML_FILE, "w") as fh:
        fh.write(r.text)
    print(f"[suite-browser] callback page saved ({len(r.text)} bytes) -> {CALLBACK_HTML_FILE}")
    # The suite answers the callback with its implicitCallback page: browser JS
    # is expected to POST window.location.hash (empty for query-mode responses)
    # back to a random /implicit/{id} URL (AbstractRedirectServerTestModule).
    # No JS runs here, so replay that step or the module waits forever.
    # thymeleaf javascript-inlines the URL as a double-quoted JS string literal;
    # accept either quote style
    m = re.search("xhr\\.open\\('POST',\\s*['\"]([^'\"]+)", r.text)
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
    got = urllib.parse.urlsplit(rewrite(raw_submit))
    if (got.scheme, got.hostname, got.port) != (expect.scheme, expect.hostname, expect.port) \
            or not got.path.startswith(f"/test/a/{ALIAS}/implicit/"):
        raise HarnessReplayError(f"unexpected implicit-submit target {raw_submit!r}")
    fragment = urllib.parse.urlsplit(redirect).fragment
    submit = urllib.parse.urlunsplit(got)
    rs = requests.post(submit, data=fragment,
                       headers={**SUITE_HDRS, "Content-Type": "text/plain"},
                       timeout=45)
    print(f"[suite-browser] implicit submit ({submit.rsplit('/',1)[-1]}) -> {rs.status_code} {rs.text[:150]}")
    if not 200 <= rs.status_code < 300:
        raise HarnessReplayError(f"suite rejected implicit submit: {rs.status_code} {rs.text[:200]}")

RESULTS_FILE = os.environ.get("RESULTS_FILE", "/tmp/stage4-vci-results.json")
CALLBACK_HTML_FILE = os.environ.get("CALLBACK_HTML_FILE", "/tmp/suite-callback-page.html")


def main() -> int:
    from mdl_config import ensure_mdl_config
    mdoc_id, issuer_url = ensure_mdl_config(CERTIFY)
    print(f"[plan] issuer={issuer_url} credential_configuration_id={mdoc_id}")

    pem_path = "e2e/compose/certify/config/mdl-issuer-trust-anchor.pem"
    trust_anchor_pem = open(pem_path).read()

    _, pub1, priv1 = gen_client_key(); pub1["kid"] = priv1["kid"] = "suite-vci-1"
    _, pub2, priv2 = gen_client_key(); pub2["kid"] = priv2["kid"] = "suite-vci-2"

    es = Esignet(ESIGNET)
    for cid, pub in (("inji-vci-suite", pub1), ("inji-vci-suite-2", pub2)):
        # No additionalConfig: the 2.0.0 image rejects it (unknown field); DPoP is
        # driven by the suite sending DPoP proofs at the token endpoint (RFC 9449).
        r = es.register_client(cid, [CALLBACK], pub)
        if r.status_code not in (200, 201):
            print(f"[plan] create failed for {cid}, trying update (PUT)")
            r = es.register_client(cid, [CALLBACK], pub, method="PUT")
        if r.status_code not in (200, 201):
            print(f"::error::could not register suite client {cid} at eSignet")
            return 1

    config = {
        "alias": ALIAS,
        "description": "OID4VCI 1.0 issuer plan vs local inji-certify mock-mdl + local eSignet (e2e harness)",
        "vci": {
            "credential_issuer_url": issuer_url,
            "authorization_server": "http://esignet:8080",
            "credential_configuration_id": mdoc_id,
            "credential_proof_type_hint": "jwt",
        },
        "credential": {"trust_anchor_pem": trust_anchor_pem},
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
                    drive_browser_url(es, url)
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
        error_excerpt = None
        if result != "PASSED":
            # pull the module's event log for the real failure reason
            try:
                entries = suite("GET", f"/api/log/{mid}").json()
                # full event log: the stall happens between suite-side steps and
                # an error filter hides the last thing the suite attempted
                print(f"[module] full event log ({len(entries) if isinstance(entries, list) else '?'} entries):")
                for e in entries if isinstance(entries, list) else []:
                    msg = e.get("msg") if isinstance(e, dict) else str(e)
                    src = e.get("source") if isinstance(e, dict) else ""
                    print(f"   [{src}] {str(msg)[:200]}")
                bad = []
                for e in entries if isinstance(entries, list) else []:
                    msg = json.dumps(e)
                    if any(k in msg.lower() for k in ("error", "exception", "fail", "invalid")):
                        bad.append(e.get("msg") if isinstance(e, dict) else msg)
                error_excerpt = bad[:4] or None
                print(f"[module] log excerpt: {json.dumps(error_excerpt)[:800]}")
            except Exception as e:
                print(f"[module] could not fetch log: {e}")
        print(f"[module] {name}: status={status} result={result}")
        results.append({"module": name, "status": status, "result": result,
                        "error_excerpt": error_excerpt})
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
                "(mock-mdl) + local eSignet. Non-PASSED results are interop findings, "
                "recorded verbatim, not harness failures.",
    }
    with open("/tmp/stage4-vci-results.json", "w") as f:
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
