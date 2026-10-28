# eSignet registration validation, local evidence

2026-10-28. No new launch/push. Last runtime40631928686 reached official
plan-info then failed before plan creation during client registration.
Runtime only retained MethodArgumentNotValidException, not exact field.

## Exact local negative and positive reproduction

Used published esignet-core1.8.0 SHA256
04cb0fe4996ec2a1e9ac5072efee1ca7fd8fcf6053ecbae077b9f2e1ba4c1836,
integration-api1.8.0 SHA256
59aa96b07c4705ddbe86b2ab16b04906ca5f53add7c0a2eec557dcf7d4a29da3,
HibernateValidator8.0.1.Final and commons-validator1.7 matching source POM.
Captured the actual SafeClassic.register_client request via substituted HTTP
transport, fresh generated PUBLIC ECJWK only. Full RequestWrapper nested bean
validation, not a retyped simplified redirect test:

| Controlled callback host | Violations | Safe property/code |
|---|---:|---|
| suite.local.test |1|request.redirectUris[0].<list element> / invalid_redirect_uri|
| suite.localhost |0|none|
| suite |0|none|

Public key service parser IdentityProviderUtil.getJWKString(actual public JWK)
also passes. Private JWK not serialized in the request or local evidence.

The local reproduction proves the submitted shape fails exactly one nested
constraint with the .test hostname under deployed-version libraries. It does
not recover the runtime rejection field from the destroyed container.

## All registration constraints checked

- RequestWrapper requestTime exact UTCyyyy-MM-ddTHH:mm:ss.SSSZ,2min leeway;
  request notnull and nested @Valid. Validation test refreshes only requestTime
  before validating the captured request to avoid deliberate aging of fixture.
- clientId/relyingPartyId notblank,100max, supported regex\\S*.
- clientName notblank,256max. Optional clientNameLangMap absent, permitted.
- publicKey nonempty map; EC/P-256/x/y/kid/alg/use from existing key generator,
  no private members; real service public-key parser passes. Public key hash
  source usesx/y fields, present; this hash was not separately executed.
- userClaims max30/non-null/each supported claim. Deployed discovery list used.
- authContextRefs min1max30/non-null/each supported. Existing three ACRs pass.
- logoUri notblank Hibernate @URL; existing public HTTPS logo passes.
- redirectUris min1max5/notnull, each notblank and RedirectURLValidator using
  UrlValidator(ALLOW_ALL_SCHEMES+ALLOW_LOCAL_URLS), no TLD relaxation added.
- grantTypes min1max3/authorization_code supported; clientAuthMethods
  min1max3/private_key_jwt supported. Deployed properties used.
- Spring-injected values were supplied to actual validator instances from exact
  source defaults. ACR provider returns known deployed three values rather than
  running remote Spring/context/resource loading. This is local validation,
  not full service runtime or auth/CSRF acceptance evidence.

## Difference from successful alpha-direct and missed tests

Same inherited SafeClassic request builder/envelope/headers and public key
helper. Main changed input is callback: successful alpha-direct used
http://localhost:18080/callback; official TLS flow uses multi-label .test.
Exact UrlValidator1.7 accepts localhost and rejects suite.local.test.
Prior API tests mocked es.register_client entirely, so nested validation was
not exercised. Prior TLS tests checked SAN/trust, not product redirect-URL
constraints. Both can pass while registration rejects a reserved TLD.

## Downstream check and remaining blind spots

Captured ACTUAL SafeClassic par-oauth-details/authenticate/auth-code request
bodies via substituted HTTP, not manual fixture reconstruction. Actual
published RequestWrapper<PushedOAuthDetailRequest/AuthRequest/AuthCodeRequest>
with deployed validators returns0violations for each. PAR urn prefix correct;
PWD factor alpha-numeric,8..30length; nested AuthChallenge validated; accepted
claim/scope lists notblank elements. Detail hash/key headers are existing
runtime-proven stage4 behavior, but current HTTPS runtime not reached them.

Remaining runtime-specific uncertainty: server CSRF cookie masking, PAR cache
state/single-use, transaction-header hash, auth-code contents, official
background execution, metadata/proof/DPoP/credential profile. These are not
claimed passed by DTO validation. Tokens/DPoP/credential request remain the
unmodified official suite's work, not rewritten by harness.

## Safe negative-path instrumentation, local only

safe_esignet.py subclasses existing SafeClassic._post, unchanged requests.
Projects controlled route+HTTP, object/error-envelope bool, exact allowlisted
errorCode and property prefix only. ExceptionHandlerAdvice emits field+
code, so a known field can be projected without copying rejected values or
messages. Unknown fields/codes become <other>. test_as_evidence verifies secret
rejectedValue/body/arbitrarymessage exclusions.21local tests pass. Not yet
integrated or pushed; no new runtime artifact currently created.

## Proposed correction, not applied

Use a single-label Docker network alias `suite` for the SUITE HTTPS host and
callback only, with matching fresh SANcert/runnerhosts/nginx alias. This name
passes the exact deployed validator; leave Certify/ASnames, schemes, ports,
protocol checks, DPoP and credential IACA/DS unchanged. `suite.localhost` also
passes local validator but loopback special treatment makes it less suitable
inside service containers. Test generated SAN/strict chain and complete
registration contract before any authorized launch. No disabling validation,
TLD allowlist changes, forced registrations or SUT edits.

## Sources inspected

https://raw.githubusercontent.com/mosip/esignet/8f662ca6c070098031f7359dbe6cc4984af84c3e/esignet-core/src/main/java/io/mosip/esignet/core/validator/RedirectURLValidator.java
https://raw.githubusercontent.com/mosip/esignet/8f662ca6c070098031f7359dbe6cc4984af84c3e/esignet-core/src/main/java/io/mosip/esignet/core/dto/ClientDetailCreateRequest.java
https://repo.maven.apache.org/maven2/io/mosip/esignet/esignet-core/1.8.0/esignet-core-1.8.0.jar

## Authorized integrated correction

Only suite transport host changed to `suite`, generated matching SAN certificate,
network alias, runner hosts, readiness and callback. Complete captured integrated
registration request passes0violations; actual source root/leaf strict SAN/chain
checks and Python loopbackTLS pass for all names. Old .test negative still fails.
SafeEsignet now integrated, explicit as-http-evidence.jsonl audit/upload allowlist.
CI check_redirect.py downloads digest-pinned public esignet-core/validator libs
and executes REAL RedirectURLValidator positive/negative regression, not fake
registration. Full local EsignetDtoContract.java retained for nested validation
reproduction.21local tests pass; no private request/key output added.
