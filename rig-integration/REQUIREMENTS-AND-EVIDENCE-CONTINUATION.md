# Requirement map and Verify evidence continuation (local design, not executed)

Anchor: user's authenticated 2026-09-07 WhatsApp message (problem statement 01, detailed). Evidence column
is limited to what run 40639293314 (branch e2e-full-run a273381) actually showed, or file presence only.

| Requirement | Status |
|---|---|
| Docker Compose Certify + Verify + suite | Combined run started 12 services incl. suite-server/mongodb, certify, esignet; Verify image started in same run (Verify preflight route returned 400, not diagnosed). Alpha/Final profile, not "1.0" labels: version alignment to the statement is unverified. |
| Programmatic runner via suite REST/python lib | Ran: pinned official conformance.py via scripts/conformance_runner.py; created plans/modules, polled, retrieved results. |
| Per-module api-testrig class + TestNG + Extent + MinIO | Native MOSIP TestNG report generation and S3 upload/readback executed for BOTH components in the run (1 test, 0 pass, 1 fail each, readback verified). Still unproven: integration into the upstream rig's own normal suite/env.endpoint path (the isolated startTestRunner path was used), only 1 module each, Slack disabled. |
| Combined run, consolidated report | combined-results.json + project-summary.html produced. Per-module native reports are separate files. |
| One-command execution | run-conformance.sh exists. Statement names run-full-stack-conformance.sh and full-stack-conformance.yml; neither name exists (workflow is native-combined.yml, manual). Not run by a clean replay. |
| Benchmark gate / fail build on regression | Gate returned failure (exit 1) truthfully. Benchmark thresholds / expected-failures / run diff: not found in repo. |
| CI/CD on release | manual workflow only on branch; push trigger removed; main untouched. |
| Docs (architecture, troubleshooting, self-certification) | README/docs exist; self-certification handoff text unverified. |

Results of the one attempt: Certify happy-flow INTERRUPTED/FAILED (cause not captured), Verify happy-flow
no official verdict (review gate). Issuer PASS is not a requirement; faithful failure reporting is valid.

## Changes in this local patch
0. (Update) Values leaving the harness are now membership-mapped, not regex-filtered: scripts/safe_names.py holds the fixed harness category set and the pinned suite condition-class list (2087 simple names from conformance-suite 23353b3, scripts/condition_classes.txt); unknown source -> other_unlisted_condition, unknown category -> handoff_incomplete_or_failed. conditions: [] (log read, no findings) is distinct from conditions_unavailable (log not read).
1. A Verify handoff stop for visual review keeps its own category (actual_result_evidence_requires_visual_review) instead of handoff_incomplete_or_failed. Other handoff errors still collapse, no upstream text.
2. status_checks_valid is null when the API returned zero status entries (Verify treats empty/null status as not blocking allChecksSuccessful: utils/Utils.java populateAllChecksSuccessful, pinned 4c42890). It is not a status-check result and says nothing about whether the credential has credentialStatus.
3. After each module the runner reads /api/log/{id} and keeps only condition class name + FAILURE/WARNING/REVIEW verdict (allowlist, capped), or conditions_unavailable. Summary shows them.
Tests: runner 8, verify-final 8, rig-integration 9 (1 skip) pass locally.

## Evidence continuation (design only)
The pinned happy-flow waits for a screenshot placeholder and ends REVIEW at best. Rules:
- Unattended CI cannot approve a screenshot: it stops at the review gate, keeps HARNESS_ERROR/awaiting-review, uploads nothing.
- Completion needs a human-reviewed PNG and a live transaction. Because the stack is torn down at job end, a continuation must run inside a replay where the user (or main) has inspected the PNG pixels and supplies its sha256; the uploader refuses unless the file hash matches, the test ID is still WAITING, and the official verdict is left as the suite computes it (REVIEW stays).
- The image is the project-rendered API view; never labelled as the native Verify UI, and no native UI screenshot is manufactured. If the user requires a native-UI shot, a manual browser capture against the local Verify UI is the only honest route.

### Pinned suite facts for completion (source: conformance-suite 23353b3, VP1FinalVerifierHappyFlow / AbstractVP1FinalVerifierTest / logging/ImageAPI / info/DBImageService)
- After a 2xx direct_post the module creates a screenshot placeholder (log entry with field `upload`=placeholder id), goes WAITING, and finishes with result REVIEW as soon as every placeholder is filled (waitForPlaceholders, 30s safety poll; placeholderFilled signals early).
- Fill route: POST /api/log/{testId}/images/{placeholder}, text/plain body `data:image/png;base64,...` (png/jpeg, size limit, max images per test); owner/admin only. Success removes `upload`, marks review needed.
- The suite's own CI fills it by a scripted browser capture of a built-in stand-in page (says it is a stand-in). That is the placeholder autoapproval we refuse.
- Not verified: whether the published Verify image ships a UI to screenshot. The current PNG is a project-rendered API view and stays labelled so.

### Live review continuation (design, not built)
Keep the stack alive while review happens, inside the same job, bounded: after PNG + sha256 are produced, the runner (1) leaves the module WAITING, (2) publishes PNG and digest to a review location, (3) polls up to N minutes for an approval record carrying the same sha256 and test ID, (4) only then POSTs the PNG to the placeholder route, (5) records REVIEW from the suite, never PASSED. No approval before the deadline -> no upload, stack torn down, row stays awaiting-review. Candidate review location: a file on a dedicated review branch pushed with the job's own token (public repo, PNG has no tokens) which main fetches raw, inspects pixels, and answers with the digest by pushing an approval file; runner polls the raw approval URL. Needs: contents write permission on that branch only in the workflow, a branch-scoped workflow edit, and the user's existing test-branch grant (not main). Alternative with no new permission surface: unattended run ends awaiting-review (current behaviour).

## Live review on the EXISTING grant (implemented locally, untested against a real runner)
No new branch, no widened token. Transport:
1. Workflow (edit of the already registered e2e-full-run.yml native-combined job; job permissions narrowed to contents: read): the attempt runs in the background (private log, setsid, exit code in a file) with CONFORMANCE_REVIEW_WINDOW=480 and a review dir outside the public evidence dir.
2. After the actual Verify result is projected and rendered, the adapter (smoke/verify-final/adapter.py review_and_upload) reads /api/log/{test} for exactly one `upload` placeholder, writes manifest.json (run id, test id, placeholder, PNG sha256, size, created_at, deadline, fixed description saying project-rendered API view, not native UI, not certification) plus the PNG, manifest last.
3. review_gate.py wait-pending sees the manifest, check-dir refuses anything but that exact pair, actions/upload-artifact publishes it as review-request-<run_id> (1 day) while the stack stays up (bounded window, max 600 s, default 480).
4. Main downloads that artifact (real attachment), inspects pixels, computes the sha256 and writes review-approvals/<run_id>-<test_id>.json on e2e-full-run with the existing credential: {"schema":1,"run_id","test_id","png_sha256","approved_at":<epoch>,"decision":"approve_faithful_view"} (exactly these keys). Push trigger is off; conformance-ci only triggers on main/pull_request.
5. The runner polls that path read-only with the job's own contents:read GITHUB_TOKEN every 15 s (contents API, not the cached raw host). validate() rejects wrong run/test/hash, extra keys, approval before manifest creation, future timestamps, expired window, or a PNG that changed. Only then it re-reads the placeholder and POSTs the PNG to /api/log/{test}/images/{placeholder}. The suite then ends the module as REVIEW; nothing is marked PASSED. No approval before the deadline -> no upload, module stays HARNESS_ERROR with review_window_expired.
Safety: the review path never runs unless CONFORMANCE_REVIEW_WINDOW is set; without it the old awaiting-review stop is unchanged. GITHUB_TOKEN is passed only to the background step (inherited by the runner subprocess via Java ProcessBuilder).
Unverified runtime assumptions: (a) the suite API log lists the placeholder entry with an `upload` field and the unauthenticated local suite lets us upload (owner/admin check); (b) a background process started in one step survives to later steps on hosted runners and exit file/log work; (c) an artifact is downloadable while the run is in progress; (d) the Java edit (pass-through args, 25 min limits when review is on) is uncompiled locally (no javac here; CI compile step runs before the product stack, so a compile error would fail cheaply); (e) approval latency vs the 480 s window depends on main reacting within about 5 minutes of the artifact appearing.
Reproducibility: scripts/build_condition_classes.py regenerates the 2087-name list from the pinned archive; regenerated output was byte-identical, list sha256 4a6b6f7697de1948c2e33b5eb33be26dc175fa314cce7b3d4b01458789352be5, locked by a test.
Coverage gaps kept explicit: --component certify|verify single orchestration unimplemented (exit 2); full plans unsupported; only selected happy flows; Verify evidence is the project-rendered PNG.

## Readiness hardening (fourth local commit)
- Upload contract at pinned ImageAPI/DBImageService: 200 with the updated entry, but also 200 with EMPTY body when no placeholder matched (findAndModify null); 400 text for bad type/size/encoding (png/jpeg, <=500 KB decoded, max 2 images), 403 for non owner/admin. Adapter therefore requires a JSON entry with `img` and without `upload`, re-reads /api/log to confirm the marker is gone, and checks GET /api/info/{id} status == WAITING immediately before POSTing. Log entries expose `upload` (LogApi doc + AbstractCondition.createBrowserInteractionPlaceholder), source-confirmed.
- Polling is httpx async with awaited sleeps; a dry run with a heartbeat task shows the loop stays responsive.
- review_gate check-dir now calls review.check_request: parsed manifest fixed keys/ids/run id/placeholder/description/deadline window, PNG hash/size/IHDR, plus provenance: projection JSON and rendered HTML hashes recorded in the manifest must match the evidence files, projection keys fixed, HTML has no script/external URL. The PNG cannot be cryptographically tied to the HTML (it is a screenshot of it); that is recorded, not claimed.
- Workflow: upload step continue-on-error; wait-exit and terminate steps always run under one absolute deadline (budget 1500 s from launch); terminate kills the owned process group only if pid+start time still match; fallback cleanup and public audit run after. Job timeout 55 min bound holds (about 10 min setup + 25 min attempt + cleanup).
- Token: GITHUB_TOKEN is popped from run_combined's environment, so compose/certify/MinIO never inherit it, and is handed only to the Verify native invocation, whose runner needs it for the read-only poll; ACTIONS tokens are always stripped. Not written to manifest/invocation/args. audit_evidence now also rejects GitHub token patterns. Secret masking by Actions applies in logs.
- Java pass-through compiled locally with stub dependencies (JDK 11 compiler); real compile still happens in CI before the stack.

## Single-component modes and the one entrypoint (local milestone, not yet run on hosted runners)

`run-full-stack-conformance.sh` is the only place the steps live; the `native-combined` workflow job calls it by phase
(`--phase prepare`, `run`, `cleanup`, `audit`) and the default `--phase all` is the one-command local run.
- `--combined` runs the Certify and Verify native rigs; `--component certify` or `--component verify` stages, compiles and runs only that rig.
  All modes use the same owned synthetic stack, MinIO, isolated suite infrastructure and cleanup. Selected happy flows only: not full official
  plans, not certification. Anything else (`--component both`, unknown component or phase, split phases without `CONFORMANCE_WORK`) exits 2 before any work.
- Workflow input `native_component` (both, certify, verify; default both) selects the rig(s). Verify-only or both keep the live review window;
  Certify-only never waits for a review (the job sees the attempt end first).
- Tests (`rig-integration/tests/test_entrypoint.py`) shim every external command and check argv, component routing, phase isolation,
  cleanup-after-failure ordering, exit status propagation, and that the workflow no longer repeats the orchestration steps.
- Condition diagnostics may now carry `requirements`: suite-authored spec reference ids (for example OID4VCI-1FINAL-8.3), shape-checked and capped, never free text.
