"""Stage 5 discovery: what Inji Verify 0.18.2 actually emits for a VP request,
and what the OIDF oid4vp-1final-verifier-test-plan demands for our variant.

Prints both verbatim so the gap analysis is evidence, not prediction:
  1. POST /v1/verify/vp-request -> the created request (transaction/request ids)
  2. GET the signed request object -> decoded JOSE header + claims (no signature)
  3. POST /api/plan on the suite with the bounded variant -> required config
"""
import sys, json, base64
import requests

VERIFY = "http://localhost:8095"
SUITE = "http://localhost:8080"
SUITE_HDRS = {"X-Forwarded-Proto": "https"}

VARIANT = {
    "vp_profile": "plain_vp",
    "credential_format": "sd_jwt_vc",
    "client_id_prefix": "redirect_uri",
    "request_method": "request_uri_signed",
    "response_mode": "direct_post",
}

def main() -> int:
    r = requests.get(f"{VERIFY}/v1/verify/did.json", timeout=30)
    print("== did.json:", r.status_code, r.text[:400])

    r = requests.post(f"{VERIFY}/v1/verify/vp-request", json={}, timeout=30)
    print("== create vp-request:", r.status_code, r.text[:600])
    if r.status_code not in (200, 201):
        print("::error::could not create a VP request")
        return 1
    body = r.json()
    request_id = body.get("requestId")
    print("== request fields:", json.dumps(body, indent=1)[:800])

    r = requests.get(f"{VERIFY}/v1/verify/vp-request/{request_id}", timeout=30)
    print("== request object fetch:", r.status_code, r.headers.get("Content-Type"))
    if r.status_code == 200:
        jwt = r.text.strip()
        h, p, _sig = jwt.split(".")
        header = json.loads(base64.urlsafe_b64decode(h + "=="))
        claims = json.loads(base64.urlsafe_b64decode(p + "=="))
        print("== request object JOSE header:", json.dumps(header, indent=1))
        print("== request object claims:", json.dumps(claims, indent=1)[:2500])

    # what does the suite demand for this variant?
    r = requests.post(f"{SUITE}/api/plan",
                      params={"planName": "oid4vp-1final-verifier-test-plan",
                              "variant": json.dumps(VARIANT)},
                      json={"alias": "inji-verify-e2e", "description": "discovery"},
                      headers=SUITE_HDRS, timeout=45)
    print("== plan create (no config):", r.status_code, r.text[:1200])
    return 0

if __name__ == "__main__":
    sys.exit(main())
