"""Shared helper: ensure the local certify advertises an mso_mdoc credential
configuration. certify 0.14 stores credential configurations in its DB via the
/credential-configurations REST API; the mock-mdl profile only activates the
MDocMockVCIssuancePlugin - it does not seed a config. The JSON we POST is
MOSIP's own sample from docs/postman-collections/inji-certify-with-mock-mdoc-vci.
Idempotent: skips the POST when an mso_mdoc config is already advertised."""
import json
import os
import time

import requests

def ensure_mdl_config(certify_base: str):
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "config", "mdl-credential-configuration.json")
    for attempt in range(6):
        md = requests.get(f"{certify_base}/v1/certify/.well-known/openid-credential-issuer",
                          timeout=30).json()
        cred_configs = md.get("credential_configurations_supported", {})
        mdoc_id = next((k for k, v in cred_configs.items() if v.get("format") == "mso_mdoc"), None)
        if mdoc_id:
            print(f"[mdl] mso_mdoc config advertised: {mdoc_id}")
            return mdoc_id, md["credential_issuer"]
        print(f"[mdl] no mso_mdoc config yet (advertised: {list(cred_configs)}); posting seed config")
        body = json.load(open(cfg_path))
        r = requests.post(f"{certify_base}/v1/certify/credential-configurations", json=body, timeout=30)
        print(f"[mdl] POST /credential-configurations -> {r.status_code}: {r.text[:300]}")
        if r.status_code not in (200, 201, 409):
            r.raise_for_status()
        time.sleep(3)
    raise RuntimeError("mso_mdoc credential configuration never became visible")
