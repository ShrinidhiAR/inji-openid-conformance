# Demo guide: what you can honestly show (branch `e2e-full-run`)

State as of 2026-10-28. Everything below is taken from recorded hosted-runner runs on this branch. Nothing here is a certification claim.

## What exists in this repository
- One command, `run-full-stack-conformance.sh` (`--component certify|verify` or `--combined`, plus `--approve-runtime`), which stages the pinned upstream api-testrig sources, compiles them, builds a pinned MinIO from source, boots one owned stack, runs the selected happy-flow modules through the native TestNG class, uploads and reads back the native reports in local MinIO, cleans up exactly what it started and audits the public evidence.
- A GitHub Actions workflow on this branch (`.github/workflows/e2e-full-run.yml`, manual dispatch, `mode=native-combined`, `native_component=both|certify|verify`).
- Not in the repo: a recorded video, and any earlier script that may have been handed over outside the repository. The repository contains only the script above. Recover any older script from the original hand-off before relying on it.

## What a viewer will see (recorded outcomes)
1. Certify, one command, default path (hosted run 40648649035): the whole lifecycle runs and cleanup is verified. The suite module `oid4vci-1_0-issuer-happy-flow` ends INTERRUPTED/FAILED because the suite check `EnsureHttpStatusCodeIsAnyOf` fails (requirement `OID4VCI-1FINAL-8.3`, the credential endpoint response status check). Root cause established (2026-11-01, local run evidence + pinned source): the pinned certify build's custom Jackson `ObjectMapper` (`certify-service` `AppConfig`) rejects unknown request fields; the suite deliberately adds a random unknown parameter to the credential request to verify the issuer ignores it (OID4VCI 1.0 Final section 8.2), parsing crashes, and the endpoint answers HTTP 500, failing the section 8.3 status check. Upstream inji-certify bug, not this harness or its configuration.
2. Combined Certify + Verify through the script's single default-all command (hosted run 40651319058, dispatch `native_component=both`, `script_path=all`; the phased workflow, run 40645764342, gave the same outcome): Certify as above, native exit code 1. Verify finishes with verdict REVIEW (revocation list fetch WARNING), which needs a human decision. The review image is a project-rendered view of the Verify v2 result API, not a native Verify UI.
3. Evidence files: `combined-results.json`, native TestNG XML and Extent HTML, `local-s3-receipt.json`, `cleanup.json`, a project summary page.

## Exact command choice
- Local demo of Certify: `./run-full-stack-conformance.sh --component certify --approve-runtime`.
- Combined: `./run-full-stack-conformance.sh --combined --approve-runtime`. Locally this gives Certify FAILED plus a deliberate Verify HARNESS_ERROR; both are recorded in the expected-failure baseline, so this run exits 0 when exactly these two outcomes occur. The Verify REVIEW result needs the review settings (a review window, a read-only token and a reviewer-committed approval file), so show it from hosted run 40651319058 or dispatch `e2e-full-run.yml` with `native_component=both`, `script_path=all`.
- Local Verify REVIEW (exercised locally 2026-11-01, demo-out11: the module ended FINISHED/REVIEW after a local human approval): add `--review local` and inspect the PNG yourself, then approve from a second terminal with `rig-integration/review_local.py` (a hash match is not proof of viewing); exact steps in the README section "Local review of the Verify image". Needs a local `google-chrome` or `chromium` on PATH - the review image is a headless screenshot of the result evidence (hosted runners ship Chrome; a fresh WSL or desktop Linux may not, and the script refuses early with a clear message).

## Expected-failure gate
The recorded baseline `baselines/expected-failures.json` lists the two known outcomes: the Certify `oid4vci-1_0-issuer-happy-flow` failure (the upstream bug, root cause above) and the deliberate local Verify `HARNESS_ERROR` when no review settings are provided. With the baseline present, the run's exit code comes from the gate: green only when the run's failures match the baseline exactly (module and result, plus status when an entry pins it), scoped to the selected components. Anything unexpected, or a listed failure that stops occurring, is red. Verify REVIEW is deliberately not in the baseline: it always asks for a human decision. The gate sees module, status and result - not which condition failed - so on a green run still read the failure rows against the baseline's recorded reason. Delete or rename the file to return to the old behavior (green only when every native rig passes).

## Not yet shown
A local bare `--combined` ends with Certify FAILED plus a deliberate Verify HARNESS_ERROR (no review settings; both are baseline entries, so the gate is green on exactly those); the Verify REVIEW result is shown locally with `--review local` (demo-out11) or from hosted run 40651319058.
Verify-only through the one-command script on a hosted runner; full official plans (only selected happy flows are run); an expected-failure baseline exercised on a hosted runner (recorded at `baselines/expected-failures.json`, wired into the local gate); a passing Certify module.

## Suggested demo steps (about 15 minutes of wall time for one component)
```sh
git clone -b e2e-full-run https://github.com/ShrinidhiAR/inji-openid-conformance.git && cd inji-openid-conformance
pip install -r scripts/requirements.txt
export JAVA_HOME=/path/to/jdk21     # needs Docker compose v2, sudo, Maven, Go, git, network
./run-full-stack-conformance.sh --component certify --approve-runtime --output demo-out
echo "exit=$?"; cat demo-out/cleanup.json; python3 rig-integration/audit_evidence.py demo-out
```
Expect exit 0 today: the Certify module still ends INTERRUPTED/FAILED (the recorded upstream bug - the result rows are unchanged), and the run is green only because that exact failure matches the recorded baseline `baselines/expected-failures.json`; `demo-out/expected-failures-verdict.json` shows `matches: true` next to the failure it covers. If anything else fails, or the pinned Certify build is fixed and the failure disappears, the run exits 1 again: the baseline matches exactly or not at all. Say so on camera. Show `demo-out/combined-results.json`, `demo-out/expected-failures-verdict.json`, the native report under `demo-out/certify/native-report/`, `cleanup.json` with `cleanup_verified: true`, and the audit line. For the hosted proof, open the run URL above. Do not run this on a machine whose `/etc/hosts` you care about without reading the script first.
