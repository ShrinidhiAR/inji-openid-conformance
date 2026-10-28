# Failure-stage audit, 2026-10-28

Run40633634789 stays two actual official failed modules, standalone report only.
Metadata FINISHED/FAILED; happyflow INTERRUPTED/FAILED. No full runner/S3/Verify,
credential issuance, signature or official chain pass. No new push/run in this audit.

## Metadata schema and algorithm

Pinned source buildMetadata reads EcdsaSecp256r1Signature2019 mapping ES256 from
unchanged copied default config. Published alpha core DTO is List<String>. Its real
Jackson serialization of this configured fixture produces ["ES256"]. The official
published suite jar's real validator rejects the minimal source-derived fixture:
`$.credential_configurations_supported.DrivingLicenseCredential.credential_signing_alg_values_supported[0]`
`string found, integer expected`.
The actual algorithm condition rejects it as expected COSE integer, got "ES256".
A contrast fixture [-7] passes those two checks, NOT an actual product/run pass.
Changing property value to string "-7" would still serialize string, not integer.
No config-only correction established; this is a source-reproduced alpha mdoc
metadata representation incompatibility, not discovery routing or trust failure.
The production service/DTO must not be patched or proxy-transformed to manufacture
green. The exact last runtime metadata/error entries were not retained; they may
contain further schema errors. Need safe type/value/count projection and exact
recognized-path error boolean plus other-error count before attributing all runtime
metadata errors to this one source-reproduced mismatch.

## Missing authorization response iss

Pinned UI Consent.js301-330 and ClaimDetails.js158-173 take configured issuer from
OAuth-details configs.issuer. Backend AuthorizationServiceImpl440-447 sets configs
from getUIConfig; application-default.properties445 issuer points to
mosip.esignet.discovery.issuer-id, itself domain URL. AuthCodeResponse contains no
iss by design: browser UI adds it. Harness omitted it in both alpha official driver
and historical stage4 bridge, so past missing-iss findings cannot be attributed to
eSignet product. API-CONTRACT-AUDIT and e2e README corrected locally.

Local alpha bridge now mirrors UI, requires details.configs.issuer equals expected
AS and forwards that actual configured value, never a guessed added issuer.
Regression exercises code/state encoding plus configured issuer forwarding and
missing/wrong configured issuer rejection. This is a source-grounded local test,
not running UI pixels or live configured-issuer evidence. Stage4 code unchanged,
boundary warning added. Earlier actual suite failures remain recorded unchanged.

## Credential HTTP failure

Official condition's success means network response, not HTTP acceptance. Expected
200/202 check failed, so status outside {200,202} is established but not exact code.
No retained runtime error body or product stack exists. Suite class forwards actual
token type in Authorization; DPoP tokens become Authorization: DPoP ... . Published
unmodified alpha AccessTokenValidationFilter accepts only prefix Bearer . Actual
published jar local fixture DPoP header skips JWT processing, sets active=false,
calls downstream. Source getCredential first rejects inactive; handler maps
NotAuthenticatedException to HTTP401 invalid_token. This is strong source/local
fixture evidence of missing DPoP credential-resource support on selected profile,
NOT proof last run returned401. Request validation could precede service, routing
could intervene. Do not rewrite DPoP to Bearer, suppress checks or change product.
Smallest confirming runtime evidence: official call event status, endpoint matches,
allowlisted VC error code, DPoP-Nonce/WWW-Authenticate presence; expected status
condition http_status and expected_status_codes. No access token/proof/header value,
body/raw error text, or credentials need preservation.

## Diagnostic completeness

Current public artifacts only condition class/verdict, metadata fetch HTTP and AS
API status/error projection. No amount of source inspection can recover discarded
previous runtime body/status. No network source remains after cleanup. New local
stage_diagnostics processes actual pinned event keys: invalid_entries, issues,
status, http_status, expected_status_codes, body_json/body(parsed only in memory),
headers(names only). Drops messages except exact fixed missing/mismatch-iss markers;
paths only exact fixed metadata path comparison, algorithms fixed literal allowlist,
error codes fixed literal allowlist, no arbitrary value passthrough. Includes
availability flags to distinguish unrecognized detail from absent error. Metadata
shape and browser configured issuer booleans captured at existing points; all
allowlisted by public audit. Collector tests reject unknown malicious strings and
private payloads. Full25local tests pass. Java fixtures real published jar, not live.
Potential next run is only for exact runtime evidence and faithful callback, NOT an
expectation these unmodified-product failures disappear. Parent approval required.

## Source URLs (pinned source retrieved and inspected)

https://raw.githubusercontent.com/inji/inji-certify/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-service/src/main/java/io/mosip/certify/services/CredentialConfigurationServiceImpl.java
https://raw.githubusercontent.com/inji/inji-certify/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-core/src/main/java/io/mosip/certify/core/dto/CredentialConfigurationSupportedDTO.java
https://raw.githubusercontent.com/inji/inji-certify/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-service/src/main/java/io/mosip/certify/filter/AccessTokenValidationFilter.java
https://raw.githubusercontent.com/mosip/esignet/8f662ca6c070098031f7359dbe6cc4984af84c3e/oidc-ui/src/components/Consent.js
https://raw.githubusercontent.com/mosip/esignet/8f662ca6c070098031f7359dbe6cc4984af84c3e/oidc-service-impl/src/main/java/io/mosip/esignet/services/AuthorizationServiceImpl.java
https://raw.githubusercontent.com/mosip/esignet/8f662ca6c070098031f7359dbe6cc4984af84c3e/esignet-service/src/main/resources/application-default.properties
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/resources/json-schemas/oid4vci/credential_issuer_metadata-1_0.json
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/vci10issuer/condition/VCIValidateCredentialSigningAlgValuesSupported.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/condition/client/AbstractCallProtectedResourceWithBearerToken.java
