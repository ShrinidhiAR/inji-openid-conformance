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
