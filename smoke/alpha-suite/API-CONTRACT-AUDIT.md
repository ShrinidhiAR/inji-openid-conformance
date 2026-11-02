# Pinned official issuer API audit

Local audit only, 2026-10-28. Not live official execution.
Source23353b36957d6466010de767c812d2c91ed37638, release-v5.3.4.
App jar SHA256177e2287e0241275251eba2c54badd37fed15c83dbbfe40244139644b073ab87.
Main unchanged. No new push/run while preparing this audit.

| Call | Exact contract and evidence | Correction / local check |
|---|---|---|
| GET/api/plan (old readiness) | TestPlanApi203-275 returns PaginationResponse object of existing instances, not definitions array | Removed incorrect readiness use. Runtime200object is correct. |
| GET/api/plan/info/oid4vci-1_0-issuer-test-plan | TestPlanApi432-464 returns object planName, modules List<Plan.Module>, variants map via VariantService.getVariantSummary | Readiness and driver share exact plan contract; wrong200object fails immediately, not180s. |
| Plan-info variants | VariantService713-867: parameter -> variantInfo, variantValues keyed by allowed string, optional notApplicableWhen | Actual pinned jar VariantService locally instantiated; complete output in fixtures/pinned-plan-info.json. All9selected values exist. sender_constrain exactly mtls/dpop. |
| Plan-info modules | VariantService551 creates Plan.Module; getter serializes testModule | Exact2names must be present, no guessed moduleName/name fallback. |
| POST/api/plan | TestPlanApi93-200 consumes JSON; query planName and variant JSON string (VariantSelectionJsonReader); returns201 {name,id,modules} | Exact201/name/id/selected modules checked. requests params JSON encoding matches official scripts/conformance.py create_test_plan. |
| POST/api/runner | TestRunner241-460 consumes application/json; query test+plan; no body for plan test, no per-module variant needed here; returns201{name,id,url} | FIX: session Content-Type application/json restored as official client/prior stage4 used. No body still. Exact201/name/id/url checked. |
| POST/api/runner/{id} | TestRunner536-566 returns200status map with id/name. New version auto-start guards prevent duplicate start | Kept exact official stage4 call, checks200and identity. Not using status map as verdict. |
| GET/api/runner/{id}/wait-state | TestRunner633-690 query states comma-separated, timeoutMs clamps1..30000; returns200{state:enum} or {timeout:true} | Exact object contract;20s longpoll under240s module budget; current info checked after timeout. |
| GET/api/runner/browser/{id} | TestRunner743-768 returns200{id,urls,visited,show_qr_code,runners}; urls strings from browser.getUrls | id+urls types checked, each URL consumed once (PAR evicts),0.5s wait avoids hot loop. |
| GET/api/info/{id} | TestInfoApi84-122 ConfigMigratingResponse(TestInfo); TestInfo getters expose testId,testName,status,result,config | Checks test identity/status/result enums. Raw config never written. Only actual status/result/test ID projected. SKIPPED added to result allowlist to match TestModule enum. |
| GET/api/log/{id} | LogApi166-180 returns List<Document>; DBEventLog53-56 source field src; Condition enum FAILURE/WARNING/INFO/SUCCESS/REVIEW | Only class-name source and enum verdict retained. REVIEW now preserved. No msg,args,config or raw body copied. |
| AS URL from suite browser | BuildRequestObjectByReferenceRedirectToAuthorizationEndpointWithoutDuplicates, eSignet application-default257/270 domain+/authorize | Exact HTTPS AS origin, /authorize, unique/nonempty client_id+request_uri only. No query rewriting or DPoP stripping. |
| GET/v1/esignet/csrf/token | Existing stage4/classic implementation, Spring6XOR masking, previously runtime-proven Java1.8 flow | Reuses SafeClassic inherited helper; token only in memory/cookie/header. |
| POST/v1/esignet/client-mgmt/oauth-client | eSignet1.8 ClientManagementController96: JSON RequestWrapper<ClientDetailCreateRequestV2>,200ResponseWrapper<ClientDetailResponse> | Existing SafeClassic shapes, envelope errors rejected; returned clientId must match fresh UUID client. No retry/update fallback. |
| POST/v1/esignet/authorization/par-oauth-details | AuthorizationController157 + PushedOAuthDetailRequest: clientId/requestUri; ResponseWrapper<OAuthDetailResponse> | Existing stage4 path preserved, exactly once; exact credentialScopes sample_vc_mdoc and no openid. No fabricated scope/acr. |
| POST/v1/esignet/authorization/authenticate | AuthorizationController RequestWrapper<AuthRequest>; PWD synthetic identity; transaction detail hash/key required | Existing safe classic request/hash flow retained, only known synthetic fixture. |
| POST/v1/esignet/authorization/auth-code | AuthorizationController98 + AuthCodeResponse DTO(code,state,redirectUri,nonce); service264-269 fills them | Historical audit correction (2026-10-28): code/state alone is NOT a faithful UI callback. Pinned Consent.js appends details.configs.issuer as iss. Current bridge omits that UI step; RequireIssInAuthorizationResponse failure is bridge-contaminated, not evidence of an eSignet product defect. See local failure-stage audit before any next run. |
| GET/test/a/alpha-official/callback?code=...&state=... | TestDispatcher aliases; AbstractRedirectServerTestModule handles callback query and renders implicitCallback template | Exact200; requests urlencode preserves values; raw page not retained. Prior captured stage4 page /tmp/s4art2 confirms escaped-slash JS rendering. |
| POST/test/a/alpha-official/implicit/{20alnum} | CreateRandomImplicitSubmitUrl makes20alnum; template POST text/plain window.location.hash; handleImplicitSubmission returns204 | Target must exact suite origin/path/noquery/nofragment. Empty query-mode fragment submitted. Exact204, no invented params/iss. |

## Variant audit result

Prior stage4 used explicit openid=plain_oauth and fapi_response_mode=plain_response.
Current pinned source conditionally excludes BOTH parameters for fapi_profile=vci.
Actual pinned jar module instantiation passes with existing9values for both selected
modules. Adding old choices is unnecessary; do not silently restore them.
Grant management gets pinned-source default disabled. No selected variant change.
The local helper also confirms14applicable plan modules with these values;
only2selected modules are requested by this harness.

## Other prerequisites and boundaries

- Certify config POST201CredentialConfigResponse.id and GET200CredentialConfigurationDTO
  credentialConfigKeyId match alpha CredentialConfigController/DTOs. Existing direct
  alpha runtime already proved those source DTOs. HTTPS metadata must match exact
  issuer/AS/nonce; no body logs. Mock seed remains known synthetic HTTP local service.
- Actual last run proved Certify TLShealthUP, AS TLSissuer match and suite TLS200.
  Transport SKI/AKI correction remains intact; no TLS/routing changes in this audit.
- Official AbstractCondition.createHttpClient uses trust-all manager and
  NoopHostnameVerifier. Suite code unmodified. Do not claim verified outbound suite
  trust/hostname. Python client and Java SUT trust use TESTCA normally.
- SDK/DPoP/proof/certificate-profile compatibility remain product outcomes to observe,
  not harness prerequisites to weaken. The official plan is alpha/noncertifiable.
-20local tests pass, including DTO-derived two-module failed-outcome projection,
  exact API methods/statuses/query/body, callback query encoding/escaped JS/204,
  wrong200fast fail, positive strict TLS and wrongSAN/wrongCA negatives.
  Mocked API rows are fixtures, NOT actual suite results.
- API progress now retains only controlled method/path-template/expected+actual HTTP.
  Failure artifact keeps category/class/lastAPI only. It never copies API config.
- Remaining runtime uncertainty: exact selected-module results against real alpha
  and active official controller/auth/background behavior have not been observed.
  Locally instantiated pinned VariantService is real jar evidence, not a live server.

## Exact source URLs inspected

https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/info/TestPlanApi.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/runner/TestRunner.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/variant/VariantService.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/testmodule/AbstractRedirectServerTestModule.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/logging/LogApi.java
