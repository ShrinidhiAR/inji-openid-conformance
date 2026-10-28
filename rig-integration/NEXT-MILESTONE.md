# Next integration milestone, 2026-10-28

Status: LOCAL PREPARATION ONLY. No additional remote run or new runtime claim.

## Requirement baseline

Original detailed statement supplied by user September7,2026 at18:28IST:
mandatory compose Certify+Verify+suite, programmatic both-role runner, TestNG class
INSIDE EACH component api-test invoking runner against same env.endpoint, combined
option/report, one command. Narrative includes same automationtests MinIO/S3 bucket.
CI named deliverable/good-to-have. Numeric benchmark not specified. Passing all
unmodified product tests is not required to implement a conformance harness.

## Local CLI correction

`run-conformance.sh` now wraps pinned unmodified official scripts/conformance.py
with checksum/license/provenance. Plan/create/start/info match published contract.
Every module has timeout, validated identity/state/result, atomic partial checkpoint.
WAITING without installed adapter becomes HARNESS_ERROR, never product FAILED.
No raw log/config/error copied; API exceptions suppressed before fixed safe category.
Explicit per-role configs/variants replace guessed defaults. Exit0 only all actual
FINISHED/PASSED,1benchmarkfail,2orchestration/setupfail. No stale result reuse.
Duplicate module names/variant expansion fail closed until explicit adapter supports
those combinations. This is an existing-environment CLI, not whole-stack command.
Five fixture tests pass; no live generic CLI validation yet. Alpha's proven driver
remains unchanged and still separate until authenticated handoff is wired in.

## Genuine isolated api-test mode design

Do NOT call InjiTestRunner.main: Certify initializes PMS/Keycloak, creates/removes
users, health threads/OTP and may cleanupDB. Verify main also environment/DBcleanup.
Both finish System.exit(0) despite failures. Calling main or using exit0 as a gate
is unsafe/wrong. Existing standalone listener is not full rig execution.

Smallest safe integration:
1. Stage pinned component api-test source+dependencies in a fresh private working
   directory. Add project-owned OpenIDConformanceTest class and a dedicated suite.
   Original product service sources/binaries remain unchanged.
2. Add an explicit project-owned isolated conformance launcher/profile compiled
   inside that component api-test. It invokes native startTestRunner discovery,
   NOT main/suiteSetup. Copy exactly ONE conformance mastertestsuite into the
   launcher-owned suite directory; preflight rejects extra suitefiles, production
   endpoints, sharedDB, or missing isolated marker. Never manipulate original rigs.
3. TestNG @BeforeSuite invokes bounded Python runner using exact verified
   env.endpoint, expectedrunid/CA and component. @DataProvider maps its fresh
   outcomes. The class fails on missing/stale/unknown/harnesserror; REVIEW stays
   review/fail by default. TestNG configuration failures must count too.
4. Configure native MOSIP BaseTestCase/ConfigManager report context only, without
   general initializePMS/Keycloak/DB helpers. This is a conformance-only rig mode,
   not a full normal MOSIP API regression suite. State that boundary in provenance.
5. Native EmailableReport uses its actual S3Adapter. Configure ONLY ephemeral local
   MinIO endpoint and generated TESTcredentials/bucket automationtests. Do not call
   external S3. Read back uploaded exactbytes/hash to prove upload (listener catches
   uploadexceptions, so report generation/log alone is not proof). S3Adapter itself
   logs accesskey; keep private logs, never artifactcredentials.
6. Independent XML outcome gate is mandatory because upstream runner exits0.
   Project summary keeps unique officialIDs and wrapped text. Never patch native
   evidence after generation; corrected view lives beside originals.

This design still needs compilation, real module class/discovery proof, isolated
MinIO upload/readback, regression guard tests and bounded approved CI execution.
If native startTestRunner cannot be initialized without general mutation paths,
stop and report exact reason, not silently substitute standalone mode as full rig.

## Verify Final/DCQL source audit

Pinned Verify4c4289026968beb535d3dbdd500947152c43f708, alpha1.0 image candidate.
Existing repo Verify compose is0.18.2 and MUST NOT silently be reused as Final.
Upstream alpha compose requires PostgreSQL/schema init; fresh isolated volumes,
servletcontext /v1/verify, HTTPS responsebase. No live Verify boot test yet.

VPRequestController POST/v2/vp-request accepts clientId,DCQLQuery,optionalnonce,
transactionId,responseCodeValidationRequired. Backend creates cryptographicnonce,
response_uri /v2/vp-submission/direct-post, response_type vp_token/direct_post.
Response AuthorizationDetails gives actual clientId/DCQL/nonce/responseURI.
Use those exact values for wallet request, not synthesized alternative identifiers.

Pinned official oid4vp-1final-verifier-test-plan acts as mockwallet. Its start()
requests URIinput then WAITING. /api/runner/{id} exposes browser.uriInputRequests
with controlledsubmitUrl. Published UI copies actual verifier openid4vp query to
that submitUrl viaGET. Adapter must validate suiteorigin/instancepath and Verify
responseURI; preserve DCQL/nonce/clientID and fetch request_uri unchanged if used.
Do not implement protocol checks in place of official suite.

Profile candidate: Final/DCQL, direct_post, URLquery, redirect_uri prefix supported
by chosen product branch must be verified against actual pinned VariantService and
Verify UI construction before config frozen. NO adapter implemented or profile
silentlychanged. mdoc versus SDJWT selection remains to ground on exact supported
Final/DCQL request and suite fixtures. No productiontrust assumptions.

Actual Verify result is POST/v2/vp-results/{transactionId}, request defaults keep
statuschecks enabled and includeClaims=false. It returns allChecksSuccessful plus
credentialresults. Must observe this, not only direct-post200. Negative modules
must use intended validation results, never automatic success. Original suite
happyflow explicitly normally finishes REVIEW after screenshot evidence. Scripted
suite evidence page is a labeled automatedstandin; not product verification proof.
A real product result screenshot/projection is needed before filling placeholder;
REVIEW must remain REVIEW and benchmarkfail, no checkbox/check weakening.

## Milestone acceptance before another push/run

- Common lifecycle fixtures and actual pinnedlibrary contract tests pass.
- Native isolatedrig launcher cannot reach unrelated account/DBmutations and runs
  exact module suite; failing test or uploadfailure independently fails gate.
- Verify deployment+wallet/result/evidence contract complete before implementation.
- One approved CI run demonstrates integration with real outcomes, even red.
- Then bounded realVerify run, percomponent gates/MinIO and combinedorchestration,
  cleancheckout replay and honest filming instructions. Not mandatory productgreen.

## Pinned source URLs inspected

https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/scripts/conformance.py
https://raw.githubusercontent.com/inji/inji-certify/8fdf71656979a72fa8263766d4dec3cc25127b76/api-test/src/main/java/io/inji/testrig/apirig/injicertify/testrunner/InjiTestRunner.java
https://raw.githubusercontent.com/inji/inji-verify/4c4289026968beb535d3dbdd500947152c43f708/api-test/src/main/java/io/inji/testrig/apirig/injiverify/testrunner/InjiTestRunner.java
https://raw.githubusercontent.com/inji/inji-verify/4c4289026968beb535d3dbdd500947152c43f708/verify-service/src/main/java/io/inji/verify/controller/VPRequestController.java
Other pinned local files inspected: VPResultController,DTOs,Constants,
VerifiablePresentationRequestServiceImpl,application.properties,alphaDockerCompose;
official BrowserControl/UriInputRequest,log-detail.js,VP1FinalVerifierHappyFlow,
AbstractVP1FinalVerifierTest,variants; MOSIP EmailableReport/S3Adapter.

## Local implementation checkpoint10:36IST

Both pinned upstream api-test projects MavencompilePASS locally. New
IsolatedRigLauncher+OpenIDConformanceTest compile against actualCertifyclasspath.
Launcher preflight restricts syntheticendpoint/marker/exactonesuite/class/listener,
disablesS3 and Slack, invokes actual native startTestRunner not main/setup.
Local HTTPfixture creates1FAILEDmodule through officialPythonlibrary invoked by
BeforeSuite, realnativeTestNG1failure and originalMOSIPreports, XMLgateexit1.
This is native discovery/classpath integration FIXTUREproof, not liveproductproof.
No remote run. Fixed provenance label: targetsource is separatelyverified, not
automatically called liveofficialsuite simply because same API responds.
Prototype fixture currently uses localpaths and needs portableguardtestharness.
MinIO disabled; mandatory uploadpath still to implement/readbacktest.
Endpoint/configconsistency beyond invocationmanifest remains a preflightTODO.

Verify exactSDK inspected: emits clientid, state=requestId, actualresponsemode/type,
nonce, responseURI, DCQL, clientmetadata(vp_formats_supported) for redirect_uri
prefix. SDK supportsdc+sd-jwt,vc+sd-jwt,ldp_vp; chosenalphaVPDCQLdescriptor lists
dc+sd-jwt,vc+sd-jwt,ldp_vc, not mdoc. So use FinalDCQLSDJWT for Verify (issuer's
mdoc credential is NOT automatically its input). RealpublishedVariantService
instantiates plain_vp/sd_jwt_vc/redirect_uri/direct_post/url_query:12modules,
nodefaults. This is candidateprofilecontract fixture, not runtimecompatibility.
ActualUIdefault uses DID for multitype, not proofredirectURIdoesn'twork; SDK
explicitlysupportsredirect_uri parameterconstruction. Need servicevalidator/
resulttrust/audiencechecks and freshDBschemamigration audit before adaptercode.

Local10:38checkpoint: nativeS3 path now optionally configured by private temporary
properties, hardrejects endpoints other than localhost/127.0.0.1/minio.local.test
and bucket other than automationtests. Uses nativeEmailableReport/S3Adapter, then
independentAWSclient reads back eachoriginalHTML andSHA256compares; failure is
not swallowed. CompiledagainstactualCertifyclasspath only, NOT runtimetested with
MinIOyet. DefaultremainsS3off. No productioncredentials or new paidresources.
Guardregression executes compiledlauncher and rejects productionendpoint, extra
suite and wrongtestclass before any report/runnermutation. Passinglocalguardtest.

## Superseding local checkpoint10:44IST

Later audit resolves earlier design TODOs above: both exactcomponentclasspath
compiles; portablefixture and guards pass; SDJWTFinalprofile and exactpublished
Verifyimage are pinned; optionalnativeS3+independenthashreadback compiled but not
runtimetested. See VERIFY-CONTRACT-AUDIT.md for current evidence and nativeheader
provenance caveat. Pure Verifybackend/wallet/resultcontract5tests pass. No live
Verifydeployment, wiredwalletadapter, realMinIOupload or combinedstack replay yet.

Next bounded integration proposal for review, not authorization to execute:
1. Complete Verifyfreshschema/preflight/HTTPS deployment and exactwalletadapter.
2. Add isolated nativefixture CI plus localMinIO, bounded private logs and hash
   receipt, no productclaims. CI timeout must surround native listener uploads.
3. Connect both adapters to percomponentrig BeforeSuite, compose run-scoped volumes
   and one combined orchestration command. Run missing prerequisites failclosed.
4. Propose ONE branch-only runtime attempt with pinned artifacts/cleanup checks.
   Review actualreport before another run. Preserve REVIEW/failures, don't chase
   green or changeproduct, and don't merge main without asking.

## Current superseding checkpoint11:03IST

Local implementation continued, nothandoffstop: genericCLI synthetic-onlyhandoffs
wired; Verifyfreshdeployment/schemajob/preflight/certgeneration added; combined
PREPAREfixture passes. run_combined.py now oneentry for bothnativecomponents and
combinedsummary but UNRUN. Native MinIOrealacceptance BOTHcomponentsPASSED locally
with fakeHTTPsuite; exactsourcebuild/provenance and portableacceptancescript added.
Publiccombinedartifactallowlist+secretpatternaudit, processgrouptimeouttests added.
See BOUNDED-RUN-PROPOSAL.md for exactproposed firstattempt and remaininguncertainties.
ActualVerifyresultPNG captured byadapter, noautomaticofficialplaceholderupload
until pixelreview. It may correctlystayHARNESS_ERROR awaitingreview. Noremote
push/run/merge or paidresources, no productcompatibilityclaim from localfixtures.
