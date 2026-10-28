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
1. A Verify handoff stop for visual review keeps its own category (actual_result_evidence_requires_visual_review) instead of handoff_incomplete_or_failed. Other handoff errors still collapse, no upstream text.
2. status_checks_valid is null when the API returned zero status entries (Verify treats empty/null status as not blocking allChecksSuccessful: utils/Utils.java populateAllChecksSuccessful, pinned 4c42890). It is not a status-check result and says nothing about whether the credential has credentialStatus.
3. After each module the runner reads /api/log/{id} and keeps only condition class name + FAILURE/WARNING/REVIEW verdict (allowlist, capped), or conditions_unavailable. Summary shows them.
Tests: runner 8, verify-final 8, rig-integration 9 (1 skip) pass locally.

## Evidence continuation (design only)
The pinned happy-flow waits for a screenshot placeholder and ends REVIEW at best. Rules:
- Unattended CI cannot approve a screenshot: it stops at the review gate, keeps HARNESS_ERROR/awaiting-review, uploads nothing.
- Completion needs a human-reviewed PNG and a live transaction. Because the stack is torn down at job end, a continuation must run inside a replay where the user (or main) has inspected the PNG pixels and supplies its sha256; the uploader refuses unless the file hash matches, the test ID is still WAITING, and the official verdict is left as the suite computes it (REVIEW stays).
- The image is the project-rendered API view; never labelled as the native Verify UI, and no native UI screenshot is manufactured. If the user requires a native-UI shot, a manual browser capture against the local Verify UI is the only honest route.
