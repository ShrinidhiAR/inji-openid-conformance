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
if r.status_code == 200:
    print(f"[seed] individual {INDIVIDUAL} already present")
    sys.exit(0)

body = {
    "requestTime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "request": {
        "individualId": INDIVIDUAL,
        "password": PASSWORD,
        "pin": "545411",
        "fullName": [{"language": "eng", "value": "Test User"}],
        "givenName": [{"language": "eng", "value": "Test"}],
        "familyName": [{"language": "eng", "value": "User"}],
        "gender": [{"language": "eng", "value": "Male"}],
        "dateOfBirth": "1990/01/01",
        "email": "test.user@example.com",
        "phone": "+911234567890",
        "country": [{"language": "eng", "value": "India"}],
        "streetAddress": [{"language": "eng", "value": "1 Test Street"}],
        "postalCode": "110001",
    },
}
r = requests.post(f"{MOCK}/identity", json=body, timeout=30)
print(f"[seed] POST /identity -> {r.status_code}: {r.text[:400]}")
r.raise_for_status()
print(f"[seed] individual {INDIVIDUAL} created")
