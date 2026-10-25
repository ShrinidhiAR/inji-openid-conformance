import sys
import time
import json
import argparse
import urllib.parse
import requests

DEFAULT_BASE_URL = "http://localhost:8080/api"

session = requests.Session()
session.headers.update({
    "Content-Type": "application/json",
    "X-Forwarded-Proto": "https"
})

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

VERIFY_VARIANTS = {}

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

def create_plan(base_url, plan_name, config_path, variants=None):
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config_data = json.load(f)

    url = f"{base_url}/plan?planName={plan_name}"
    if variants:
        v_str = urllib.parse.quote(json.dumps(variants))
        url += f"&variant={v_str}"

    response = session.post(url, json=config_data)
    response.raise_for_status()
    plan_info = response.json()
    plan_id = plan_info.get("id") or plan_info.get("_id")
    print(f"[INFO] Created test plan: {plan_id} for {plan_name}")
    return plan_id, plan_info.get("modules", [])

def run_test_module(base_url, plan_id, test_module_name):
    url = f"{base_url}/runner?test={test_module_name}&plan={plan_id}"
    res = session.post(url)
    res.raise_for_status()
    test_info = res.json()
    test_id = test_info.get("id") or test_info.get("_id")
    print(f"\n[INFO] Running module {test_module_name} (ID: {test_id})...")

    while True:
        status_res = session.get(f"{base_url}/log/{test_id}")
        if status_res.status_code == 200:
            status_data = status_res.json()
            status = status_data.get("status")
            result = status_data.get("result")

            if status in ["FINISHED", "REVIEW"] or result in ["PASSED", "FAILED", "WARNING"]:
                print(f"[RESULT] {test_module_name} -> Status: {status}, Result: {result}")
                return {
                    "module": test_module_name,
                    "test_id": test_id,
                    "status": status,
                    "result": result
                }
        time.sleep(3)

def main():
    parser = argparse.ArgumentParser(description="Programmatic OpenID Conformance Runner")
    parser.add_argument("--component", choices=["certify", "verify"], help="Component to test")
    parser.add_argument("--combined", action="store_true", help="Run both certify and verify")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL")
    parser.add_argument("--output", default="conformance-results.json", help="Output JSON path")
    args = parser.parse_args()

    wait_for_server(args.base_url)

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
    else:
        print("[ERROR] Please specify --component [certify|verify] or --combined")
        sys.exit(1)


    all_results = {}
    for comp, plan_name, config_file, variants in plans_to_run:
        print(f"\n================ Starting {comp.upper()} Plan ================")
        plan_id, modules = create_plan(args.base_url, plan_name, config_file, variants)
        comp_results = []
        for mod in modules:
            mod_name = mod.get("testModule") if isinstance(mod, dict) else mod
            res = run_test_module(args.base_url, plan_id, mod_name)
            comp_results.append(res)
        all_results[comp] = comp_results

    with open(args.output, "w", encoding="utf-8") as out:
        json.dump(all_results, out, indent=2)
    print(f"\n[INFO] All results written to {args.output}")

if __name__ == "__main__":
    main()