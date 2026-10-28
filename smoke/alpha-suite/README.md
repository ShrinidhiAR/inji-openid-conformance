# Local preparation only, not launched

Bounded official issuer metadata + happy-flow modules, unchanged DPoP scheme.
Pinned suite image digest and its embedded git.properties verified locally:
release-v5.3.4, source23353b36957d6466010de767c812d2c91ed37638.
Registry index and amd64 manifest are in image-lock.json. Runtime plan-info
checks remain fail-closed before creating a plan.

TLS: new runtime local TEST CA, SAN leaves, Java normal trust store copy plus CA,
runner normal CA validation, TLS1.2/1.3 nginx. HTTPS issuer/JWKS/audience/scope
mapping/proof/callback contract. Private artifacts never uploaded. Runtime
requires sudo for temporary /etc/hosts aliases and restores exact original.
Complete alpha DB initialization reused; old0.14 files remain unchanged.

mDL signer: independent TEST IACA signs document signer leaf. Plugin extractor
accepts one leaf; MdocGenerator attaches exactly that leaf, root out of band.
This is the required shape for a single IACA-issued DS cert, no need to insert
root in credential or patch plugin. Actual published generator locally tested
with this input, producing valid signature/8digests/holder/MSOtimes. That is
local fixture evidence, NOT fresh live alpha issuance or official chain pass.
Suite may expose other certificate-profile/metadata/protocol findings.

Only actual module IDs/status/results -> fresh selected-module JSON -> existing
standalone MOSIP EmailableReport/TestNG gate. Interrupted/failed modules stay
red. Existing full rig InjiTestRunner and S3/MinIO upload are NOT executed by
this entrypoint. No whole-plan/certification claim.

Local adapter regression replayed archived real0.14 INTERRUPTED/FAILED result;
1executed/0passed/1failed,exit1. Screenshot visually checked. Report's default
header contains apitest-commons library commit/branch, NOT SUT revision. Keep
explicit run-provenance beside report; do not present that header as alpha code.

Not yet dispatched. Remaining runtime uncertainties: Docker Compose rendering,
Java trust-store path/type with actual images, effective AS issuer under TLS,
actual suite plan response/API shapes, browser replay and downstream DPoP denial.
First actual run must config --quiet before boot and retain only allowlisted
public certs, summary/conditions, fresh outcome JSON, cleanup and inspected report.
No raw suite config/logs, credential, nonce, tokens, proof or private keys.

No extra standalone DPoP diagnostic. Metadata/happy-flow official failures are
meaningful outcomes; no rewriting to Bearer, bypassing TLS or weakening checks.

## Failed first HTTPS run and local diagnostic repair

Run40628938343 stopped at generic TLS readiness timeout before official modules.
It retained no per-origin responses or transport classes, so cause is unknown.
Do not claim a certificate, DNS or application defect from that artifact.

Local repair: reuse safe_http_evidence.summarize/Recorder; each controlled origin
has route/status/media type/shape/health/error-code progress, a180s cap, last
failure category and origin-specific exception. TLS verification errors retain
numeric verify_code and allowlisted category/classes only and fail promptly.
Docker inspection retains service label + lifecycle/exit/OOM/health enum only;
terminal process failures abort promptly. Health starting/unhealthy is evidence only during the bounded warmup, not a terminal process failure. Known nginx stderr categories are
projected without text/paths/hostnames. No new config fix or security weakening
is assumed without diagnostic evidence. Unit tests exercise HTTP502 timeout,
TLS SAN mismatch, dead proxy, lifecycle redaction and safe proxy projection.

Run40630283599 fail-fast diagnosed transport verify_code85 on first Certify
request. Its public leaf/root reproduce OpenSSL strict errors missing AKI85 and
SKI86, though non-strict verification passed. Minimal correction adds SKI/AKI
to transport root/leaf only. Every generated runtime CA+leaf/SAN now passes
openssl strict checks before services start. Local regression also requires
wrong hostname and wrong chain to fail and actual Python strict loopback TLS
to pass. This corrects our deployment profile, not SUT or official assertions;
credential IACA/document-signer profile is unchanged.
