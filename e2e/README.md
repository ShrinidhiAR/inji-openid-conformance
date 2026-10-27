# Running the full end-to-end stack locally

This directory contains the real end-to-end setup: the official OpenID
Foundation conformance suite, a local eSignet (authorization server) with the
MOSIP mock identity system, and Inji Certify (mDL / `mso_mdoc` profile). No
fixtures: every stage either reaches the real services or fails.

Status is tracked stage by stage below. Nothing here claims a passing
conformance result; the suite plans are alpha and not certifiable, and the
point of this harness is to expose exactly where the real stack interoperates
and where it does not.

## Prerequisites

* Docker with the compose plugin
* About 8 GB of free RAM (six Java services plus MongoDB)
* Free host ports: 8080 (suite), 8082 (mock identity), 8088 (certify gateway),
  8090 (eSignet), 8099 (certify-app debug)
* Python 3.10+ with `requests` and `cryptography` for the validation scripts
  (`pip install requests cryptography`)

## One-time setup

```bash
git checkout e2e-full-run
docker network create e2e-net || true   # shared by all stacks
```

## Stage 1 - conformance suite boots

```bash
docker compose -f docker/docker-compose.yml up -d
# wait for the API (plain HTTP; every API call needs this header):
curl -sf -H "X-Forwarded-Proto: https" http://localhost:8080/api/plan
```

The suite image needs `MONGODB_HOST` and `BASE_URL` plus dummy
`OIDC_GOOGLE_*` / `OIDC_GITLAB_*` client env vars; the compose file already
sets them. Plain-HTTP API calls must send `X-Forwarded-Proto: https` or the
suite answers with redirects/400s.

## Stage 2 - local eSignet + scripted login

```bash
docker compose -f e2e/compose/esignet/docker-compose.yaml up -d
python e2e/scripts/stage2_validate.py
```

The script registers a client, drives the full authorization-code flow over
REST (no browser), and exchanges the code for tokens.

Seeded mock identity (public MOSIP test data, not real credentials):

* individual id `1774231323`
* password `Mosip@123`
* PIN `545411`
* OTP `111111`

## Stage 3 - local Certify (mDL) + direct scripted issuance

```bash
# generate the mDL issuer key+cert once (writes e2e/config/mdl-issuer-key-cert.json)
python e2e/scripts/mdl_issuer_key.py

docker compose -f e2e/compose/esignet/docker-compose.yaml up -d
docker compose -f e2e/compose/certify/docker-compose.yaml up -d
python e2e/scripts/stage3_validate.py
```

The script seeds the `DrivingLicenseCredential` (`mso_mdoc`, doctype
`org.iso.18013.5.1.mDL`) credential configuration into Certify's database via
its admin API, then runs the OID4VCI flow end to end: eSignet login, token,
nonce, credential request with a wallet key proof, and verifies the returned
mDoc.

KNOWN ISSUE (verified version-pair incompatibility): eSignet 2.0.0 (the Go
engine) issues RFC 9068 access tokens (`typ: at+jwt`). Inji Certify 0.14.0
(Spring Boot 3.2.3) rejects them: `GET /v1/certify/nonce` answers 401 with
`WWW-Authenticate: error="invalid_token", error_description="... JOSE header
typ (type) at+jwt not allowed"`. The token signature itself verifies against
eSignet's JWKS. The only other official certify image,
`injistack/inji-certify-with-plugins:1.0.0-alpha.1` (alpha, not certifiable),
does not boot with the published 0.14-era configuration: it embeds
verify-service 0.18.2 (interactive authorization requests) and fails with
`UnsatisfiedDependencyException` on `p12KeyExtractor`.

CURRENT ROUTE BEING VALIDATED (branch e2e-full-run): eSignet was swapped to
the official JAVA line image `mosipid/esignet-with-plugins:1.8.0` - the
parity baseline for 2.0.0, with PAR (`/oauth/par`) and DPoP support, whose
access tokens are signed via MOSIP kernel `SignatureUtil.getJWSHeader` that
sets no `typ` header. Pairing status: source-supported hypothesis, NOT a
documented tested combination (certify 0.14.0 was officially QA'd against
esignet 1.6.2, same Java/kernel signing path but no PAR/DPoP). The login
driver is the classic REST API (`esignet_classic.py`: oauth-details ->
authenticate -> auth-code; no /flow/execute - that was the Go engine).
Push-triggered runs currently execute stages 2-3 only (evidence for
login/token + direct issuance); stages 1/4/5 run on manual dispatch until
the swap is validated.

## Stage 4 - real OIDF suite vs local Certify

```bash
docker compose -f e2e/compose/esignet/docker-compose.yaml up -d
docker compose -f e2e/compose/certify/docker-compose.yaml up -d
docker compose -f docker/docker-compose.yml up -d
python e2e/scripts/stage4_vci_plan.py
```

Runs the real `oid4vci-1_0-issuer-test-plan` (mdoc variant) from the suite
container against Certify and writes per-module results to
`stage4-vci-results.json`. Results are reported exactly as the suite returns
them (PASSED / FAILED / WARNING / REVIEW / INTERRUPTED).

Certify's issuer identifier is `http://certify:8090`; an nginx gateway
container serves that name and rewrites the RFC 8615 well-known location
(`/.well-known/openid-credential-issuer`) onto Certify's servlet path, which
is how the real suite resolves issuer metadata.

## Troubleshooting (verified causes, not guesses)

| Symptom | Verified cause | Fix in this branch |
| --- | --- | --- |
| eSignet login fails with `FET-1005` / `invalid_credentials` | eSignet fetches the mock signing certs once at startup and fails closed if mock-identity-system is not listening yet | `mock-ready` gate container blocks eSignet startup until the mock actuator returns 200 |
| Client registration answers `invalid_input` | eSignet 2.0.0 client management strict-decodes JSON; unknown fields (e.g. `additionalConfig`) are rejected | send only fields 2.0.0 knows |
| Token endpoint answers 401 `invalid_client` for private_key_jwt | three real requirements: `aud` must be the issuer URL (not the token endpoint), a `kid` header is required, and the ES256 signature must be raw `R||S` (64 bytes), not DER | `e2e/scripts/esignet_flow.py` builds the assertion accordingly |
| Suite module start answers 404 | the suite's runner API starts a module with `POST /api/runner/{id}`, there is no `/start` suffix | stage 4 driver uses the correct endpoint |
| Suite cannot fetch issuer metadata | the suite builds `scheme://authority/.well-known/openid-credential-issuer` (RFC 8615); Certify serves it under `/v1/certify` | nginx gateway rewrite in `e2e/compose/certify` |

## Tearing down

```bash
docker compose -f docker/docker-compose.yml down
docker compose -f e2e/compose/certify/docker-compose.yaml down
docker compose -f e2e/compose/esignet/docker-compose.yaml down
docker network rm e2e-net
```
