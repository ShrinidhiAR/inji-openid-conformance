# Demo guide: what you can honestly show (branch `e2e-full-run`)

State as of 2026-10-28. Everything below is taken from recorded hosted-runner runs on this branch. Nothing here is a certification claim.

## What exists in this repository
- One command, `run-full-stack-conformance.sh` (`--component certify|verify` or `--combined`, plus `--approve-runtime`), which stages the pinned upstream api-testrig sources, compiles them, builds a pinned MinIO from source, boots one owned stack, runs the selected happy-flow modules through the native TestNG class, uploads and reads back the native reports in local MinIO, cleans up exactly what it started and audits the public evidence.
- A GitHub Actions workflow on this branch (`.github/workflows/e2e-full-run.yml`, manual dispatch, `mode=native-combined`, `native_component=both|certify|verify`).
- Not in the repo: a recorded video, and any earlier script that may have been handed over outside the repository. The repository contains only the script above. Recover any older script from the original hand-off before relying on it.

## What a viewer will see (recorded outcomes)
1. Certify, one command, default path (hosted run 40648649035): the whole lifecycle runs and cleanup is verified. The suite module `oid4vci-1_0-issuer-happy-flow` ends INTERRUPTED/FAILED because the suite check `EnsureHttpStatusCodeIsAnyOf` fails (requirement `OID4VCI-1FINAL-8.3`, the credential endpoint response status check). The root cause in the product or the configuration is not established.
2. Combined Certify + Verify via the phased workflow (hosted run 40645764342): Certify as above. Verify finishes with verdict REVIEW (revocation list fetch WARNING), which needs a human decision. The review image is a project-rendered view of the Verify v2 result API, not a native Verify UI.
3. Evidence files: `combined-results.json`, native TestNG XML and Extent HTML, `local-s3-receipt.json`, `cleanup.json`, a project summary page.

## Not yet shown
Verify-only through the one-command script on a hosted runner; full official plans (only selected happy flows are run); any expected-failure baseline (none recorded); a passing Certify module.

## Suggested demo steps (about 15 minutes of wall time for one component)
```sh
git clone -b e2e-full-run https://github.com/ShrinidhiAR/inji-openid-conformance.git && cd inji-openid-conformance
pip install -r scripts/requirements.txt
export JAVA_HOME=/path/to/jdk21     # needs Docker compose v2, sudo, Maven, Go, git, network
./run-full-stack-conformance.sh --component certify --approve-runtime --output demo-out
echo "exit=$?"; cat demo-out/cleanup.json; python3 rig-integration/audit_evidence.py demo-out
```
Expect exit 1 with a FAILED Certify module today. That is the recorded result, so say so on camera. Show `demo-out/combined-results.json`, the native report under `demo-out/certify/native-report/`, `cleanup.json` with `cleanup_verified: true`, and the audit line. For the hosted proof, open the run URL above. Do not run this on a machine whose `/etc/hosts` you care about without reading the script first.
