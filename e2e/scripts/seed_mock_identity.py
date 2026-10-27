"""Seed the mock individual into mock-identity-system (Java stack, 0.13.0).

POST /v1/mock-identity-system/identity (IdentityController.createIdentity).
The official init.sql creates the schema but seeds no identity. PWD auth
compares HMAC(password) against the stored hash (AuthenticationServiceImpl),
which addIdentity computes from this plaintext field. Idempotent: skips when
the individual already exists (GET returns 200)."""
import json
import sys
import time

import requests

MOCK = "http://localhost:8082/v1/mock-identity-system"
INDIVIDUAL = "1774231323"
PASSWORD = "Mosip@123"

r = requests.get(f"{MOCK}/identity/{INDIVIDUAL}", timeout=15)
# The mock returns HTTP 200 with an error envelope for a MISSING individual
# ({"response": null, "errors": [{"errorCode": "invalid_individual_id"}]}) -
# status code alone is not proof of presence (observed in run 40522449921,
# where seeding was wrongly skipped and kyc-auth then failed).
if r.status_code == 200 and (r.json().get("response") or {}).get("individualId"):
    print(f"[seed] individual {INDIVIDUAL} already present")
    sys.exit(0)
print(f"[seed] GET /identity -> {r.status_code}: {r.text[:200]} (not present, seeding)")

# Field set mirrors mock-identity-schema.json "required" (0.13.0); a missing
# required field comes back as HTTP 200 + errors envelope (observed run
# 40525224755: invalid_region/invalid_locality/invalid_encodedphoto/...).
def lang(v):
    return [{"language": "eng", "value": v}]

body = {
    "requestTime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "request": {
        "individualId": INDIVIDUAL,
        "password": PASSWORD,
        "pin": "545411",
        "fullName": lang("Test User"),
        "givenName": lang("Test"),
        "familyName": lang("User"),
        "middleName": None,
        "nickName": None,
        "preferredUsername": None,
        "gender": lang("Male"),
        "dateOfBirth": "1990/01/01",
        "streetAddress": lang("1 Test Street"),
        "locality": lang("Test Locality"),
        "region": lang("Test Region"),
        "country": lang("India"),
        "postalCode": "110001",
        "preferredLang": "eng",
        "encodedPhoto": "/9j/4AAQSkZJRg==",  # minimal placeholder, schema requires the key
        "email": "test.user@example.com",
        "phone": "+911234567890",
        "zoneInfo": "Asia/Kolkata",
        "locale": "en",
    },
}
r = requests.post(f"{MOCK}/identity", json=body, timeout=30)
print(f"[seed] POST /identity -> {r.status_code}: {r.text[:400]}")
r.raise_for_status()
errors = (r.json().get("errors") or [])
if errors:
    print(f"::error::mock identity seed rejected: {errors}")
    sys.exit(1)
print(f"[seed] individual {INDIVIDUAL} created")
