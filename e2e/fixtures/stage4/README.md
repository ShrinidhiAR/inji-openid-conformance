# Stage 4 bootstrap fixtures — SYNTHETIC, single-capture

These files document the interface shapes the stage4 classic PAR bridge
implements, captured from the bounded local contract test
(`e2e/scripts/test_stage4_classic_bridge.py`, stub servers, stub values).

- `suite-authorize-url.txt` — the PAR redirect URL shape the suite exposes
  while a module is WAITING (`client_id` + `request_uri` only, per the suite
  source `BuildRequestObjectByReferenceRedirectToAuthorizationEndpointWithoutDuplicates`).
- `authorize-callback.txt` — the callback URL the driver builds from the
  classic auth-code response and GETs against the suite redirect endpoint.
- `implicit-submit-page.html` — reproduction of the suite's thymeleaf-rendered
  implicitCallback page (shape verified against a real captured page in stage 1).

They are NOT evidence of protocol conformance and NOT captures of a live run.
Live-run evidence is the `stage4-vci-results` artifact uploaded by the
e2e-full-run workflow (per-module status/result + full redacted suite event
logs + the rendered callback page).
