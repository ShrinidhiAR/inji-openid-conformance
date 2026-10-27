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
    return requests.request(method, SUITE + path, **kw)

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

def main() -> int:
    md = requests.get(f"{CERTIFY}/v1/certify/.well-known/openid-credential-issuer", timeout=30).json()
    cred_configs = md.get("credential_configurations_supported", {})
    mdoc_id = next((k for k, v in cred_configs.items() if v.get("format") == "mso_mdoc"), None)
    if not mdoc_id:
        print("::error::no mso_mdoc credential configuration advertised by certify")
        return 1
    issuer_url = md["credential_issuer"]
    print(f"[plan] issuer={issuer_url} credential_configuration_id={mdoc_id}")

    pem_path = "e2e/compose/certify/config/mdl-issuer-trust-anchor.pem"
    trust_anchor_pem = open(pem_path).read()

    _, pub1, priv1 = gen_client_key(); pub1["kid"] = priv1["kid"] = "suite-vci-1"
    _, pub2, priv2 = gen_client_key(); pub2["kid"] = priv2["kid"] = "suite-vci-2"

    es = Esignet(ESIGNET)
    for cid, pub in (("inji-vci-suite", pub1), ("inji-vci-suite-2", pub2)):
        r = es.register_client(cid, [CALLBACK], pub,
                               additional_config={"dpop_bound_access_tokens": True})
        if r.status_code not in (200, 201):
            print(f"[plan] create failed for {cid}, trying update (PUT)")
            r = es.register_client(cid, [CALLBACK], pub, method="PUT",
                                   additional_config={"dpop_bound_access_tokens": True})
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
    print(f"[plan] {len(module_names)} modules to run")

    results = []
    for name in module_names:
        print(f"\n[module] === {name} ===")
        r = suite("POST", "/api/runner", params={"test": name, "plan": plan_id})
        if r.status_code != 201:
            print(f"[module] create failed: {r.status_code} {r.text[:300]}")
            results.append({"module": name, "status": "HARNESS_ERROR", "result": None})
            continue
        mid = r.json().get("id")
        r = suite("POST", f"/api/runner/{mid}/start")
        print(f"[module] started id={mid} -> {r.status_code}")

        status = result = None
        deadline = time.time() + 600
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
                b = suite("GET", f"/api/runner/browser/{mid}").json()
                urls = b.get("urls") or []
                if not urls:
                    continue
                try:
                    drive_browser_url(es, urls[0])
                except Exception as e:
                    print(f"[module] browser drive failed: {e}")
                    # let the module decide what a dead front-channel means
                    time.sleep(5)
                continue
            info = suite("GET", f"/api/info/{mid}").json()
            status = info.get("status")
            result = info.get("result")
            break
        print(f"[module] {name}: status={status} result={result}")
        results.append({"module": name, "status": status, "result": result})

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
    for r0 in results:
        if r0["result"] != "PASSED":
            print(f"::warning::{r0['module']}: {r0['status']}/{r0['result']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
