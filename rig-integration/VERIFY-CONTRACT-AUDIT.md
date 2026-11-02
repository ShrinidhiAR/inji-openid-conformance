# Verify Final/DCQL pre-implementation audit

Local source audit only, not live deployment or conformance result.
Pinned source4c4289026968beb535d3dbdd500947152c43f708.

## Deployment blind spot found before run

Upstream alpha docker-compose/db-init/init.sql is stale: vp_submission lacks
response_code,response_code_expiry_at,response_code_used and primary/uniquekeys;
its vp_token/presentation_submission NOTNULL differs from entity nullable wallet
error handling. Current db_scripts/inji_verify/ddl/verify-vp_submission.sql defines
all those fields/keys. Copying upstream DockerCompose init blindly would produce
runtime500 at submission/readback. Use exact current fullDDL in freshschema, verify
columns/constraints preflight, never ALTER an existing/shareddatabase. Othermodels
must each be matched to currentDDL, not assumed by table existence/readiness200.
The selected image still needs digest/publication provenance check and actual
binaryDTO/schema cross-check before liveuse. No profile/versionchange silently.

## Wallet and verifier result

Use Final/DCQLSDJWT, not issuer'smdoc: actual DTO/validator supportedformats are
ldp_vc,dc+sd-jwt,vc+sd-jwt. Official profile supports sd_jwt_vc. Pinned actualjar
VariantService with plain_vp,sd_jwt_vc,redirect_uri,direct_post,url_query produces
12modules,nodefaults. This is candidatecontract not compatibilityproof.

VerifySDK OpenID4VPVerification103-123 constructs URLquery from actualrequest:
client_id,requestIdasstate,response_mode,response_type,nonce,response_uri,dcql_query,
client_metadata.vp_formats_supported for redirect_uri/decentralized_identifier.
No requestobject is needed for selectedredirect_uri/urlquery, which suitepermits;
request_uri_signed is explicitly prohibited with redirect_uri. Need preserveexact
actualclientIdresponseURIrelationship and validateexpectedendpoint; no rewriting.
SDK normalUI uses sessionrequest/cookie. Non-session v2/vp-request route also exists
and uses samebusinesslogic, but don't call it exactUI flow; label backendAPIadapter.

OfficialBrowserControl uriInputRequests exposes controlledsubmitUrl via GET/api/runner/{id}, NOT GET/api/runner/browser/{id}; log-detail.js
submits actualopenid4vpquery viaGET. Validate exactsuiteorigin/moduleauthorization
endpoint first. Never use arbitraryincomingURL and never send unrelatedcontext.

Directpostsuccess means acceptedsubmission only. POST/v2/vp-results/{transactionId}
with skipStatusChecks=false,statusCheckFilters=[],includeClaims=false triggersreal
verification and returns allChecksSuccessful plus percredentialchecks. Require
nonemptycredentialResults, matchingtransaction and allrequiredchecks, not vacuous
allMatch true. Keep no claims/token/rawerrors in public artifacts. Certificate or
issuertrust source remains to audit, never inventtrustedissuer orskipstatuschecks.

Pinned officialhappyflow creates screenshotplaceholder and endsREVIEW, which is
notPASSED and staysreddefaultbenchmark. Evidence screenshot must showrealproduct
verificationresult. Suite's own automatedevidencepage says standin for directpost
status, insufficient as soleproductverificationproof. Keep officialverdict intact.

## Native rig local proof

Both exactpinned api-test sourceprojects Mavencompile. New conformance-only classes
compiled against EACH actualclasspath and invoked each native startTestRunner with
oneisolatedsuite, BeforeSuitePythonofficiallibrary and fakeHTTPsuite. Both1FAILED
fixturemodule -> nativeTestNG1failedrow/nativeMOSIPreports/XMLgateexit1. This is
fixtureproofonly. No main/suiteSetup/PMS/Keycloak/DBmutation paths called.
NativeEmailableReport unconditionally callsSlack; explicitemptywebhook precludes
sending. MinIOoff until isolatednativeS3/readback implementation. Localfixture
source currentlydeveloperpathprototype, notportableCI acceptance yet.

## Relevant inspected source paths

- docker-compose/db-init/init.sql versus db_scripts/inji_verify/ddl/*.sql
- models/VPSubmission and AuthorizationRequestCreateResponse
- VPRequestController,VPResultController,VPSubmissionController
- services/impl/VerifiablePresentationRequestServiceImpl
- services/impl/VerifiablePresentationSubmissionServiceImpl
- validator/DcqlValidator,DTOs and SDKOpenID4VPVerification
- pinned suite AbstractVP1FinalVerifierTest,VP1FinalVerifierHappyFlow,
  BrowserControl/UriInputRequest/log-detail.js and VariantService actualjar

Observed URLs supporting SDK/DTO/suite contracts:
https://raw.githubusercontent.com/inji/inji-verify/4c4289026968beb535d3dbdd500947152c43f708/inji-verify-sdk/src/components/openid4vp-verification/OpenID4VPVerification.tsx
https://raw.githubusercontent.com/inji/inji-verify/4c4289026968beb535d3dbdd500947152c43f708/verify-service/src/main/java/io/inji/verify/dto/dcql/CredentialQueryDto.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/vp1finalverifier/VP1FinalVerifierHappyFlow.java

## Published image and binary checkpoint, 10:44 IST

Image now pinned in smoke/verify-final/image-lock.json. OCI config labels and
extracted jar git.properties both identify exact4c4289026968beb535d3dbdd500947152c43f708.
Actual published DTO with Spring's Jackson ParameterNamesModule, BeanValidation
and DcqlValidator accepts candidate Final/DCQLSDJWT request with0violations.
This is a classpath fixture, not a request accepted by a running service.
All four unchanged current table DDLfiles copied with SHA256/provenance into
smoke/verify-final/db; init creates NEW verify schema only, no existingDBmigration.
Database initialization and schema preflight still need runtime demonstration.

Actual vcverifier-jar-1.9.0 SdJwtVerifier.verifyJWTSignature reads x5c[0], extracts
leafpublickey and verifies JWS. Do not claim issuer JWKS resolution or independent
PKItrustchainvalidation from this code path. Official AbstractCreateSdJwtCredential
propagates credential.signing_jwk.x5c into generated SDJWT header, so provide a
fresh synthetic signingkey/certificate consistently, not patch the verifier.
Statusverification and holderproof are separate required resultchecks; signature
success alone does not satisfy them. No product compatibility result yet.

Backend API pure contract helpers now preserve SDK queryparameters and exactly
pin responseURI/clientID/profile, scope wallet submit to sameHTTPSsuiteorigin and
actualmodule /test/{id}/authorize (no alias configured), correlate nonempty result
rows, and project only booleans/counts without tokens/claims/errors. Five local
contracttests pass. No HTTPwalletadapter is installed in genericCLI yet.

Both staged native projects now compile; portableclasspath fixture executes both
with1FAILEDfakeHTTPmodule mapped to realnativeTestNG1fail/exit1. Guardtests cover
production/wrongcomponent/wrongport/path/userinfo/extrasuite/wrongclass. Project
launcher refuses nonlocal suiteorigin except explicit fixtureOnly loopback mode.
OptionalS3 code compiles both, independenthashreadback pending liveMinIOproof.

Native original fixture HTML pixels inspected: correct1total/0pass/1fail and
component/moduleID. Native header incorrectly embeds upstream dependency git
commit/releasebranch, not actual componentcommit, and long stacktrace clips at
rightedge. Originals remain untouched; use project-owned report/provenance beside
them and warn against reading that native header as deployment provenance.

Correction: read uriInputRequests through GET/api/runner/{id}. The separatelynamed
GET/api/runner/browser/{id} does NOT return it in this pinned build. Both actual
source and published TestRunner bytecode confirm distinction. Host stays suite,
matching existing TESTTLS SAN/config, not a new suite.local.test hostname.

Result API code's allChecksSuccessful permits empty statuschecks and null
holderproof. Projectprojection independently shows nonemptycredentialcount,
explicit schema/signature, expiry, holderproof and statuscount/validity, rather
than turning top-level true into strongerproof. Chosen happyflow carries status
reference, so noempty-status acceptance should be described as verifiedrevocation.

Official ImageAPI source confirms GET/api/log/{id}/images includes placeholders,
POST/api/log/{id}/images/{placeholder} expects PNG/JPEG dataURI max500KB/twoimages,
sets officialREVIEW and notifies placeholderFilled. Do not use new-image endpoint
as though it fills an existingplaceholder. An actualgeneratedprojection screenshot
must be inspected and bound to actualresult before upload. No uploadimplemented.

Local adapter.py now implements exactpinned happyflow only: scoped sameorigin
GET/api/runner/{id}, freshbackendAPIrequest, preservedSDKquery, exactmodulewallet
handoff, realPOSTresultchecks and tokenfreeprojection. Negatives rejected, no
arbitraryURLs/redirects, nativeHTTPerrors safe. It is NOT installed in genericCLI,
NOT runtimevalidated, and deliberately cannot manufacture an officialterminal
verdict or upload uninspectedresult evidence. Otherselectedmodules remain gap.

## Superseding checkpoint11:02IST

GenericCLI now explicitly enables synthetic-only handoffs, reusing actualissuer
UIbridge and FinalVerifyhappyflowadapter. Unsupportedmodule choices failclosed.
Verifydeployment extension uses pinnedpublishedimage+freshdedicatedDB/schemajob,
all20column/type/nullability and VPkeys/defaultassertions beforeboot; readonly
routevalidationpreflight separate from actualrequest/resultacceptance. Combined
PREPAREfixture passed, no servicebooted. OriginalTLSstrictprofiletest still passes.

REAL MinIO nativeacceptance now passed locally for BOTH actualcomponentrigs:
exactofficialsource9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a built with Go;
loopbackservice freshprivatecredentials+automationtests; nativeS3Adapter uploads
2originalHTMLs/component; independentAWSreadback SHA256matches each. NativeTestNG
FAILEDfixture still gatesexit1. This is realstorage/nativeupload but FAKEHTTPsuite,
not liveproductconformance. Processstopped/privateTEMPremoved. Reproduction through
build_minio.py+tests/minio_native_acceptance.py; binarysourcehash/provenancechecked.
This supersedes earlier compiled-onlyMinIOcaveat for that localacceptancepath.

run_combined.py now prepares/boots ownedstack, provisions exactsyntheticissuer,
executes both isolatednativeJVMs with genericCLIhandoffs and mandatorynativeMinIO,
combines outcomes, restoreshosts/deletesprivateconfig/downvolumes/checksresidue.
It is NOT runtimevalidated. JVM externalgroupkillbounds childPython. Verifyactual
projectionPNG is captured but officialplaceholder upload is deliberately absent
until actualpixels reviewed. Consequently happyflow can end HARNESS_ERROR awaiting
review, never forgedPASSED or hiddenWAITING. A useful firstboundedintegrationrun
can demonstrate deployment/request/result+nativeS3 even with truthfulredgate.
