# MOSIP Inji OpenID Conformance Automation

Automated local execution and CI/CD pipeline integration for MOSIP Inji Certify (OpenID4VCI) and Verify (OpenID4VP) components using the official OpenID Foundation Conformance Suite.

## Table of Contents
1. [Overview](#overview)
2. [Architecture and flow](#architecture-and-flow)
3. [Repository structure](#repository-structure)
4. [Prerequisites](#prerequisites)
5. [Quick Start](#quick-start)
6. [Installation and setup (step by step)](#installation-and-setup-step-by-step)
7. [Usage](#usage)
8. [Configuration](#configuration)
9. [API reference (conformance suite endpoints used)](#api-reference-conformance-suite-endpoints-used)
10. [Output format](#output-format)
11. [Test cases](#test-cases)
12. [Test data](#test-data)
13. [Troubleshooting](#troubleshooting)
14. [Known limitations](#known-limitations)

## Overview

MOSIP's Inji stack issues and verifies digital credentials. **Inji Certify** is the issuer (OpenID for Verifiable Credential Issuance, OpenID4VCI) and **Inji Verify** is the verifier (OpenID for Verifiable Presentations, OpenID4VP). The OpenID Foundation publishes a Conformance Suite that checks whether an implementation follows these specifications.

Running the suite by hand through its web UI is slow and hard to repeat. This project automates it:

* Docker Compose starts the conformance suite and its MongoDB database.
* A Python runner (`scripts/conformance_runner.py`) calls the suite's REST API: it creates a test plan, runs every test module in it, waits for each to finish, and records the outcome.
* Results are written to `conformance-results.json`, a plain JSON file meant to be read by a TestNG / ExtentReports test rig or a CI job.

## Architecture and flow

```text
 conformance_runner.py                 Conformance Suite (Docker)          System under test
 ---------------------                 --------------------------          -----------------
 1. GET  /api/plan  (wait until up) -->  server :8080  <--> MongoDB :27017
 2. POST /api/plan  + JSON config   -->  creates plan, returns its modules
 3. for each module:
      POST /api/runner?test=..&plan=.. -> starts the module  ------------>  Inji Certify (issuer)
      GET  /api/log/{test_id}  (poll) <-  status + result    <-----------  or Inji Verify (verifier)
 4. write conformance-results.json
```

Step by step:

1. The runner waits until the suite's API answers.
2. It reads the JSON config for the component (`docker/configs/...`) and creates a test plan, passing the plan name and variant selection as query parameters.
3. The suite returns the list of test modules in that plan.
4. For each module the runner starts it and polls its log every 3 seconds until the status is `FINISHED` or `REVIEW`, or a result of `PASSED`, `FAILED` or `WARNING` is reported.
5. All module outcomes are saved to one JSON file, grouped by component (`certify`, `verify`).

## Repository structure

```text
inji-openid-conformance/
├── docker/
│   ├── docker-compose.yml                    # Conformance suite + MongoDB
│   └── configs/
│       ├── certify-issuer-config.json        # Test plan config for Inji Certify (issuer)
│       └── verify-verifier-config.json       # Test plan config for Inji Verify (verifier)
├── scripts/
│   └── conformance_runner.py                 # REST API driver
├── .gitignore
└── README.md
```

## Prerequisites

* Docker Desktop (with WSL2 Mirrored Mode enabled on Windows)
* Python 3.14+ with `requests`
* Free local ports `8080` (conformance suite) and `27017` (MongoDB)
* Enough memory for several containers: 8 GB RAM minimum, 16 GB comfortable
* A running Inji Certify and/or Inji Verify instance reachable at the URLs in the config files (see [Configuration](#configuration)). This repository does not start them.

## Quick Start

1. **Start the Conformance Suite & MongoDB:**
   ```powershell
   docker compose -f docker/docker-compose.yml up -d
   ```

2. **Run Certify (Issuer) Conformance Tests:**
   ```powershell
   python scripts/conformance_runner.py --component certify
   ```

3. **Output Artifact:**
   Test results are automatically exported to `conformance-results.json` for integration into TestNG / ExtentReports test rigs.

## Installation and setup (step by step)

1. **Clone the repository**
   ```powershell
   git clone https://github.com/ShrinidhiAR/inji-openid-conformance.git
   cd inji-openid-conformance
   ```

2. **Install Docker Desktop** and make sure it is running. On Windows, enable WSL2 and virtualization (BIOS/UEFI setting) first.

3. **Install Python and the dependency**
   ```powershell
   python --version
   pip install requests
   ```
   Optionally use a virtual environment (`python -m venv venv`, then activate it). `venv/` is git-ignored.

4. **Start the suite**
   ```powershell
   docker compose -f docker/docker-compose.yml up -d
   docker compose -f docker/docker-compose.yml ps
   ```
   Both `conformance-mongo` and `conformance-server` should be listed as running. The suite UI opens at <http://localhost:8080>.

5. **Check the config files** in `docker/configs/` point at your Inji instances (see [Configuration](#configuration)).

6. **Run the runner** (see [Usage](#usage)).

7. **Stop everything when finished**
   ```powershell
   docker compose -f docker/docker-compose.yml down
   ```
   Add `-v` to also delete the MongoDB volume (`mongo_data`).

## Usage

```text
python scripts/conformance_runner.py [--component {certify,verify}] [--combined]
                                     [--base-url URL] [--output PATH]
```

| Option | Meaning | Default |
|---|---|---|
| `--component certify` | Run the Inji Certify issuer plan (`oid4vci-1_0-issuer-test-plan`) | none |
| `--component verify` | Run the Inji Verify verifier plan (`oid4vp-1final-verifier-test-plan`) | none |
| `--combined` | Run both plans, certify first, then verify | off |
| `--base-url` | Base URL of the suite REST API | `http://localhost:8080/api` |
| `--output` | Where to write the JSON summary | `conformance-results.json` |

You must pass either `--component` or `--combined`; otherwise the script prints an error and exits with code 1.

Examples:

```powershell
python scripts/conformance_runner.py --component certify
python scripts/conformance_runner.py --component verify --output verify-results.json
python scripts/conformance_runner.py --combined
python scripts/conformance_runner.py --component certify --base-url http://localhost:8080/api
```

Console output uses the prefixes `[INFO]`, `[RESULT]` and `[ERROR]`.

## Configuration

### Docker Compose (`docker/docker-compose.yml`)

| Service | Image | Port | Notes |
|---|---|---|---|
| `mongo` | `mongo:6.0` | 27017 | Data kept in the `mongo_data` volume |
| `server` | `registry.gitlab.com/openid/conformance-suite:latest` | 8080 | Dev profile; points at Mongo through `spring.data.mongodb.uri`. The `oauth.clients.*` values are dummy placeholders for local use |

### Test plan configs (`docker/configs/`)

* `certify-issuer-config.json`: the `server.discoveryUrl` is the Inji Certify issuer metadata endpoint (`http://certify.local:8081/.well-known/openid-credential-issuer`). `client.client_id` and `client.client_secret` are test placeholders.
* `verify-verifier-config.json`: `verifier.presentation_definition_uri` is the Inji Verify presentation definition endpoint (`http://verify.local:8082/presentation-definition`).

Edit these URLs to match where your Inji Certify / Inji Verify instances run. If you use the `.local` host names, map them in your hosts file (for example `127.0.0.1 certify.local verify.local`) or replace them with real addresses. Config files may be saved with a UTF-8 BOM; the runner handles that.

### Variants (`scripts/conformance_runner.py`)

`CERTIFY_VARIANTS` selects the test plan options sent to the suite for the issuer plan:

| Variant | Value |
|---|---|
| `fapi_profile` | `vci` |
| `credential_format` | `sd_jwt_vc` |
| `client_auth_type` | `private_key_jwt` |
| `sender_constrain` | `dpop` |
| `vci_authorization_code_flow_variant` | `wallet_initiated` |
| `vci_credential_encryption` | `plain` |
| `vci_grant_type` | `authorization_code` |
| `authorization_request_type` | `simple` |
| `fapi_request_method` | `unsigned` |

`VERIFY_VARIANTS` is empty, so the verifier plan uses the suite defaults.

## API reference (conformance suite endpoints used)

These are the endpoints of the OpenID Conformance Suite that the runner calls. All paths are relative to the base URL (`http://localhost:8080/api`). The runner sends `Content-Type: application/json` and `X-Forwarded-Proto: https` on every request. No authentication is used (local dev profile).

### `GET /plan`
Health check. The runner retries every 3 seconds, for up to 90 seconds, until it gets HTTP 200.

### `POST /plan?planName={plan}&variant={url-encoded JSON}`
Creates a test plan.

* Query: `planName` (for example `oid4vci-1_0-issuer-test-plan`); `variant` (URL-encoded JSON object of variants, omitted when empty).
* Body: the JSON config file contents.
* Response: JSON containing the plan id (`id` or `_id`) and `modules`, the list of test modules (each an object with `testModule`, or a plain name).

### `POST /runner?test={module}&plan={planId}`
Starts one test module of a plan.

* Response: JSON containing the test id (`id` or `_id`).

### `GET /log/{testId}`
Returns the state of a running or finished test. The runner reads two fields:

* `status`: for example `FINISHED`, `REVIEW`.
* `result`: for example `PASSED`, `FAILED`, `WARNING`.

The runner polls every 3 seconds and stops when `status` is `FINISHED` or `REVIEW`, or `result` is `PASSED`, `FAILED` or `WARNING`.

Example (shape only):

```text
POST http://localhost:8080/api/plan?planName=oid4vp-1final-verifier-test-plan
     body: contents of docker/configs/verify-verifier-config.json
```

For the full API, see the OpenID Conformance Suite documentation.

## Output format

`conformance-results.json` maps each component to a list of module results:

```json
{
  "certify": [
    { "module": "<test module name>", "test_id": "<id>", "status": "<status>", "result": "<result>" }
  ],
  "verify": [
    { "module": "<test module name>", "test_id": "<id>", "status": "<status>", "result": "<result>" }
  ]
}
```

Only the components you ran appear. The values above are placeholders showing the structure, not real results. The file is git-ignored.

## Test cases

These are procedures to follow and the outcome to expect. They describe what the harness should do; they are not recorded results.

| ID | Procedure | Expected outcome |
|---|---|---|
| TC-01 Suite starts | Run `docker compose -f docker/docker-compose.yml up -d`, then `docker compose -f docker/docker-compose.yml ps` | `conformance-mongo` and `conformance-server` are running; <http://localhost:8080> loads |
| TC-02 Health wait | Start the runner while the suite is still booting | Console prints `[INFO] Waiting for Conformance Suite...` and then `[INFO] Conformance suite is up and running.` |
| TC-03 Suite not running | Run `docker compose -f docker/docker-compose.yml down`, then run the runner | After 90 seconds the runner stops with a `TimeoutError` saying the suite did not become ready |
| TC-04 No component given | Run `python scripts/conformance_runner.py` with no options | Prints `[ERROR] Please specify --component [certify\|verify] or --combined` and exits with code 1 |
| TC-05 Certify plan | With Inji Certify reachable, run `--component certify` | A plan is created (`[INFO] Created test plan: <id> ...`), each module is run, a `[RESULT]` line is printed per module, and `conformance-results.json` has a `certify` list |
| TC-06 Verify plan | With Inji Verify reachable, run `--component verify` | Same as TC-05, with a `verify` list in the output |
| TC-07 Combined run | Run `--combined` | Certify plan runs first, then verify; the output file has both `certify` and `verify` lists |
| TC-08 Custom output path | Run `--component certify --output out.json` | Results are written to `out.json` instead of the default file |
| TC-09 Missing config | Rename `docker/configs/certify-issuer-config.json` and run `--component certify` | The runner fails with a file-not-found error before any test starts (restore the file afterwards) |
| TC-10 Invalid config JSON | Break the JSON syntax in a config file and run the matching component | The runner fails with a JSON parse error before any test starts (restore the file afterwards) |
| TC-11 BOM tolerance | Save a config file with a UTF-8 BOM (as PowerShell does) and run the matching component | The config loads normally |
| TC-12 Git hygiene | Run the runner, then `git status` | `conformance-results.json` is not listed as untracked (it is in `.gitignore`) |

## Test data

All values are placeholders for local testing and are not real credentials:

* Config client: `client_id` = `conformance-test-client`, `client_secret` = `test-secret`.
* Issuer metadata URL: `http://certify.local:8081/.well-known/openid-credential-issuer`.
* Presentation definition URL: `http://verify.local:8082/presentation-definition`.
* Conformance suite OAuth client values in `docker-compose.yml`: `dummy-client-id` / `dummy-client-secret`.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `TimeoutError: Conformance suite ... did not become ready` | The suite is not running or still starting. Check `docker compose -f docker/docker-compose.yml ps` and `docker compose -f docker/docker-compose.yml logs server`, wait a minute, retry |
| Port 8080 or 27017 already in use | Stop the program using the port, or change the left side of the port mapping in `docker-compose.yml` and pass the new address with `--base-url` |
| Docker says virtualization is not enabled | Turn on virtualization in BIOS/UEFI and enable WSL2 in Windows features |
| Image pull fails for `conformance-suite` | Check your internet connection and that you can reach `registry.gitlab.com`; retry `docker compose ... pull` |
| `FileNotFoundError` for a config file | Run the script from the repository root, because config paths are relative (`docker/configs/...`) |
| `ModuleNotFoundError: No module named 'requests'` | Run `pip install requests` |
| HTTP 4xx/5xx from `POST /plan` | The plan name, variants or config are not accepted by your suite version. Check the runner's plan names against the suite's available plans in the web UI at <http://localhost:8080> |
| Connection errors from the suite to Inji Certify / Verify | The URLs in `docker/configs/` are not reachable from the suite container. Check host names, ports and firewall |
| A test module never finishes | See Known limitations below |
| Garbled first character when reading a config in a text editor | The file has a UTF-8 BOM; this is harmless for the runner |

## Known limitations

* The runner polls each test with no overall time limit. A module that waits for a manual step (for example a wallet action in the suite UI) will keep the runner waiting until the step is done in the UI at <http://localhost:8080>.
* The compose file starts only the conformance suite and MongoDB. Inji Certify and Inji Verify must be started separately.
* A Java/TestNG bridge is not part of this repository; `conformance-results.json` is the hand-off format for that kind of integration.
* The `latest` tag of the suite image is not pinned, so behavior can change when the image is updated.
