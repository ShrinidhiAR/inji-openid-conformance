"""Programmatic runner for the OpenID Foundation Conformance Suite.

Drives the suite's REST API to create a test plan for Inji Certify (OpenID4VCI
issuer) and/or Inji Verify (OpenID4VP verifier), run every test module in the
plan, poll each module until it finishes, and write a JSON summary that can be
consumed by a TestNG / ExtentReports test rig.

Usage:
    python scripts/conformance_runner.py --component certify
    python scripts/conformance_runner.py --component verify
    python scripts/conformance_runner.py --combined
"""
import os
import sys
import time
import json
import uuid
import argparse
import urllib.parse
from datetime import datetime, timezone
import requests

# Base URL of the conformance suite REST API (started by docker/docker-compose.yml).
DEFAULT_BASE_URL = "http://localhost:8080/api"

# One shared HTTP session so headers are applied to every request.
session = requests.Session()
# The suite is served over plain HTTP locally; X-Forwarded-Proto makes it behave as if behind HTTPS.
session.headers.update({
    "Content-Type": "application/json",
    "X-Forwarded-Proto": "https"
})

# Variant selection for the OID4VCI issuer plan (sent as the "variant" query parameter).
# Each key picks one option of a test-plan dimension in the conformance suite.
CERTIFY_VARIANTS = {
    "fapi_profile": "vci",
    "credential_format": "sd_jwt_vc",
    "client_auth_type": "private_key_jwt",
    "sender_constrain": "dpop",
    "vci_authorization_code_flow_variant": "wallet_initiated",
    "vci_credential_encryption": "plain",
    "vci_grant_type": "authorization_code",
    "authorization_request_type": "simple",
    "fapi_request_method": "unsigned"
}

# The verifier plan is run with the suite's default variants.
VERIFY_VARIANTS = {}

# Poll GET /plan until the suite answers 200, so we do not start before it has booted.
# Raises TimeoutError after `timeout` seconds.
def wait_for_server(base_url, timeout=90):
    start = time.time()
    print(f"[INFO] Waiting for Conformance Suite at {base_url}...")
    while time.time() - start < timeout:
        try:
            res = session.get(f"{base_url}/plan")
            if res.status_code == 200:
                print("[INFO] Conformance suite is up and running.")
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    raise TimeoutError(f"Conformance suite at {base_url} did not become ready in {timeout}s.")

# Create a test plan via POST /plan, uploading the JSON config file for the system under test.
# Returns (plan_id, list_of_test_modules).
def create_plan(base_url, plan_name, config_path, variants=None):
    # utf-8-sig tolerates a BOM (Windows PowerShell writes one when creating files).
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config_data = json.load(f)

    # The plan name is a query parameter; variants are URL-encoded JSON.
    url = f"{base_url}/plan?planName={plan_name}"
    if variants:
        v_str = urllib.parse.quote(json.dumps(variants))
        url += f"&variant={v_str}"

    response = session.post(url, json=config_data)
    response.raise_for_status()
    # Different suite versions return the plan id as "id" or "_id".
    plan_info = response.json()
    plan_id = plan_info.get("id") or plan_info.get("_id")
    print(f"[INFO] Created test plan: {plan_id} for {plan_name}")
    return plan_id, plan_info.get("modules", [])

# Start one test module of a plan via POST /runner, then poll GET /log/{test_id}
# until it reaches a terminal state. Returns a small dict with the outcome.
def run_test_module(base_url, plan_id, test_module_name):
    url = f"{base_url}/runner?test={test_module_name}&plan={plan_id}"
    res = session.post(url)
    res.raise_for_status()
    test_info = res.json()
    test_id = test_info.get("id") or test_info.get("_id")
    print(f"\n[INFO] Running module {test_module_name} (ID: {test_id})...")

    # Poll every 3 seconds. Note: there is no overall timeout here; a module that
    # waits for manual interaction will keep this loop running.
    while True:
        status_res = session.get(f"{base_url}/log/{test_id}")
        if status_res.status_code == 200:
            status_data = status_res.json()
            status = status_data.get("status")
            result = status_data.get("result")

            # Terminal condition: terminal STATUS only. The suite's official
            # automation library (scripts/conformance.py in the conformance-suite
            # repo) waits on status alone; a result value is only read once the
            # module has reached a terminal status, so an intermediate value can
            # never be mistaken for a final one. INTERRUPTED is terminal too: the
            # outcome is recorded and the benchmark gate fails it.
            if status in ["FINISHED", "REVIEW", "INTERRUPTED"]:
                print(f"[RESULT] {test_module_name} -> Status: {status}, Result: {result}")
                return {
                    "module": test_module_name,
                    "test_id": test_id,
                    "status": status,
                    "result": result
                }
        time.sleep(3)

# Entry point: parse arguments, build the list of plans to run, execute them, save results.
def main():
    parser = argparse.ArgumentParser(description="Programmatic OpenID Conformance Runner")
    parser.add_argument("--component", choices=["certify", "verify"], help="Component to test")
    parser.add_argument("--combined", action="store_true", help="Run both certify and verify")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL")
    parser.add_argument("--output", default="conformance-results.json", help="Output JSON path")
    args = parser.parse_args()

    # Block until the suite is reachable.
    wait_for_server(args.base_url)

    # Each entry: (component name, suite plan name, config file, variants).
    plans_to_run = []
    if args.combined:
        plans_to_run = [
            ("certify", "oid4vci-1_0-issuer-test-plan", "docker/configs/certify-issuer-config.json", CERTIFY_VARIANTS),
            ("verify", "oid4vp-1final-verifier-test-plan", "docker/configs/verify-verifier-config.json", VERIFY_VARIANTS)
        ]
    elif args.component == "certify":
        plans_to_run = [("certify", "oid4vci-1_0-issuer-test-plan", "docker/configs/certify-issuer-config.json", CERTIFY_VARIANTS)]
    elif args.component == "verify":
        plans_to_run = [("verify", "oid4vp-1final-verifier-test-plan", "docker/configs/verify-verifier-config.json", VERIFY_VARIANTS)]
        # Neither --component nor --combined was given.
    else:
        print("[ERROR] Please specify --component [certify|verify] or --combined")
        sys.exit(1)


    # Maps component name -> list of per-module results. A "run" block records
    # when this output was produced; the api-testrig bridge refuses to gate on a
    # results file without a fresh timestamp, so a stale file from an older run
    # cannot pass the benchmark.
    run_started_at = datetime.now(timezone.utc)
    all_results = {"run": {
        "id": str(uuid.uuid4()),
        "started_at": run_started_at.isoformat(),
        "tool": "conformance_runner.py"
    }}
    for comp, plan_name, config_file, variants in plans_to_run:
        print(f"\n================ Starting {comp.upper()} Plan ================")
        plan_id, modules = create_plan(args.base_url, plan_name, config_file, variants)
        comp_results = []
        for mod in modules:
            # Modules may be returned as dicts ({"testModule": ...}) or plain names.
            mod_name = mod.get("testModule") if isinstance(mod, dict) else mod
            res = run_test_module(args.base_url, plan_id, mod_name)
            comp_results.append(res)
        all_results[comp] = comp_results

    # Write the summary file atomically (default: conformance-results.json, which
    # is git-ignored): a crash mid-write can never leave a truncated file that a
    # later gate run might mistake for complete results.
    tmp_output = args.output + ".tmp"
    with open(tmp_output, "w", encoding="utf-8") as out:
        json.dump(all_results, out, indent=2)
    os.replace(tmp_output, args.output)
    print(f"\n[INFO] All results written to {args.output} (run id {all_results['run']['id']})")

if __name__ == "__main__":
    main()