# Conformance pipeline: architecture, automation, handoffs, certification path, troubleshooting

Companion to `docs/DEMO-GUIDE.md` (what to show) - this is how it works. Everything below matches the code on `e2e-full-run` and recorded runs (hosted 40648649035 / 40651319058; local demo-out5 through demo-out15, 2026-11-01). Nothing here is a certification claim.

## 1. Architecture

One command (`run-full-stack-conformance.sh`, phases `prepare -> run -> cleanup -> audit`) drives four subsystems:

- **Owned synthetic stack** (generated compose, never committed): built per run by `smoke/alpha-suite/prepare_runtime.py` with the Verify services from `smoke/verify-final/deployment.py`. Contains `certify-app` (compiled from pinned inji-certify `8fdf7165`), esignet + mock identity, the official OpenID conformance-suite image (release-v5.3.4, digest-pinned) + its MongoDB, real `injistack/inji-verify-service:1.0.0-alpha.1` + its postgres (image locked in `smoke/verify-final/image-lock.json`, source commit verified from the image's own OCI labels), an nginx `tls-gateway` (the role the suite's reference `httpd` plays), and a local MinIO built from a pinned source archive (`rig-integration/build_minio.py`) standing in for the pipeline's S3. TLS is a per-run local CA; names resolve through a hosts-file append that cleanup restores exactly.
- **Staged native rigs**: the pinned upstream api-testrig sources (inji-certify `8fdf7165`, inji-verify `4c428902`) are cloned, injected with this repo's isolated TestNG suite (`rig-integration/isolated-suite/`, launcher `inji.conformance.IsolatedRigLauncher`), and compiled with Maven (`stage_isolated.py`). Upstream repositories are never modified; the injection happens only in the work directory.
- **Runner**: `scripts/conformance_runner.py` (details in section 2), driven by the launcher over the suite's REST API.
- **Evidence + gate**: every run writes an output directory (`combined-results.json`, native `testng-results.xml` + Extent HTML, `local-s3-receipt.json` proving upload+readback, `cleanup.json`, `expected-failures-verdict.json`, `failure.json` on early death) and is judged against the user-owned baseline `baselines/expected-failures.json`: green only when the run's failures match the baseline exactly (see the gate section in DEMO-GUIDE).

`docs/architecture-full-stack.png` (`docs/architecture.pptx` editable) shows the same topology.

## 2. How the API automation works

No UI is touched anywhere. The runner is built on the suite's official Python automation library (vendored, hash-pinned: `vendor/openid-suite/conformance.py` - the same library the suite's own `run-test-plan.py` uses) and speaks the suite's REST API:

1. `POST /api/plan` - create the plan for the selected variant with a generated configuration (`suite_contract.py` variant + the component driver's `configuration()`).
2. `POST /api/runner` - create the module instance (`oid4vci-1_0-issuer-happy-flow` / `oid4vp-1final-verifier-happy-flow`), capture its test id.
3. `POST /api/runner/<id>` - start the module.
4. Poll `GET /api/info/<id>`: while the suite reports `WAITING`, perform the required handoffs (section 3), without consuming the module's time budget while waiting on a human review.
5. When the module is `FINISHED`/`INTERRUPTED`, fetch `GET /api/log/<id>` and the result, project them into rows `{module, test_id, status, result, conditions}` - per condition only its name, result and requirement ids are kept; raw logs, bodies and secrets are never copied out.

The native TestNG class runs this same runner inside the staged api-testrig, so results land in the standard TestNG/Extent reports, which are then uploaded to the local MinIO and read back. `scripts/testng_bridge.py` separately maps the rows to TestNG/JUnit XML (PASSED -> passed, WARNING -> passed with note, FAILED -> failed, anything else -> skipped).

## 3. Handoff handling, per component

Both handoff drivers fail closed: any unexpected module, origin, URL shape or configuration raises an audited category (`scripts/safe_names.py`) instead of improvising.

- **Certify (issuer, browser handoffs)**: the suite's happy flow requires wallet-browser interactions. `smoke/alpha-suite/official_driver.py` reads the suite's exposed browser URLs from `GET /api/runner/<id>` and performs them programmatically: the mock-identity login, the esignet consent, and the credential issuance against `https://certify.local.test:8443`, with evidence projections (never bodies) under `<out>/<component>-evidence/`. The suite's spec-mandated random unknown parameters (OID4VCI 1.0 Final section 8.2) are what exposed the pinned certify build's HTTP 500 bug (upstream issue inji/inji-certify#1156).
- **Verify (verifier, wallet-backend handoff)**: `smoke/verify-final/adapter.py` plays the wallet backend: creates a transaction on Verify's real v2 API (`/v2/vp-request`), submits it through the suite's handoff URL, then calls `/v2/vp-results/<txn>` and records a projection of the result. The suite then ends the module REVIEW on purpose: the revocation-list fetch is a WARNING a human must weigh. The runner renders the result evidence to a PNG (headless Chrome/Chromium) and parks it in a private review request (`smoke/verify-final/review.py`): hosted runs approve through a read-only GitHub token + reviewer-committed approval file; local runs through `rig-integration/review_local.py` (inspect the image, approve its sha256 from a second terminal, 600-second window). The placeholder is uploaded only after byte-identical re-verification; the suite itself records REVIEW, never an auto-PASSED.

## 4. How to submit for self-certification

This repository is the engineering pipeline, not a submission. Where a real submission stands today:

1. **Scope**: a submission runs the FULL official plans (all variants and modules), not the selected happy flows this repo runs. The pipeline supports them in principle (the runner accepts any module list); full-plan runs have not been executed and are recorded as "not yet shown".
2. **Known blocker for Certify**: the pinned inji-certify build fails `OID4VCI-1FINAL-8.3` because it rejects the spec-mandated unknown request parameter with HTTP 500 (root cause established 2026-11-01: the custom Jackson `ObjectMapper` bean in certify-service `AppConfig`; upstream issue inji/inji-certify#1156 with a candidate one-line fix). A certification attempt needs an inji-certify build with that fix.
3. **Verify**: the happy flow ends REVIEW by design (revocation-list WARNING); a human records the decision through the review flow. That is the suite working as intended, not a failure.
4. **Mechanics**: certification submissions go through the OpenID Foundation's certification program (<https://openid.net/certification/>): run the official conformance-suite plans for your profile against your deployment, keep the suite's own logs, and submit them with the program's declaration. This repo's per-run evidence directories keep the equivalent artifacts (module results, native reports, condition projections) for exactly that purpose.
5. **Honesty rule**: nothing in this repo turns a REVIEW or a baselined failure into a pass. The gate's green means "matches the recorded, user-owned baseline", and the verdict file says so next to the reasons.

## 5. Troubleshooting

First move, always: read `<output>/failure.json` (stage + error class) when a run dies early, and `<output>/expected-failures-verdict.json` when it completes. Runs are silent until the readiness stage by design.

| Symptom | Meaning | Fix |
| --- | --- | --- |
| Instant silent exit, prompt back, only `failure.json` in the output | early stage died with output discarded (stage names the step) | `cat` the failure file; `compose_validate` = docker daemon or stale stack (below) |
| `fresh_evidence_directory_required` | output dir exists (dead runs still leave one) | use a new `--output` name; never reuse |
| `cat: .../native-<component>-classpath: No such file` | that component's rig was never compiled in this `CONFORMANCE_WORK` | run `--phase prepare` with that component selected (each work dir holds exactly what its prepare built) |
| Stale `conformance-<id>-*` containers after a failed run | the run's own cleanup was interrupted | `python3 rig-integration/fallback_cleanup.py --locator $CONFORMANCE_WORK/owned/locator.json` (scoped to that project only; verifies zero leftovers) |
| `refusing: --review local ... Chrome or Chromium` (preflight) | the review image is a headless screenshot and no browser is installed | install google-chrome or chromium, rerun |
| Verify HARNESS_ERROR `actual_result_evidence_requires_visual_review` | deliberate: no review settings, the evidence needs a human | intended for bare runs (baseline entry); use `--review local` to decide it live |
| Review window expired (600s) | approval came too late | clean review dirs (`review_local.py clean --work ...`) and rerun with a fresh output name |
| `review directories already exist` | a previous `--review local` left them | same clean command |
| First-ever `pull`/`up` very slow | images download on first prepare only | expected; reruns are ~80s from cache - do not `docker system prune` the cached images |
| hosts-file worries | cleanup restores `/etc/hosts` byte-exactly and verifies it | if a run was killed mid-flight, `fallback_cleanup` (above) restores it from the locator's backup |
| Gate red with `expected_but_not_observed` | a baselined failure did NOT occur (fixed upstream? baseline stale) | good news wearing a red coat: re-record the baseline deliberately |
| Gate green but you didn't expect it | read `matched_expected_failures` - green only ever means "matches the recorded baseline", and a rig that never ran (fallback row) does not match | if in doubt, the raw rows in `combined-results.json` are unmodified |

Known honest limitations: the gate matches module/status/result, not which condition failed (read the verdict against the baseline's recorded reason); the runner's scope is selected happy flows; Verify REVIEW always requires a human, every run.
