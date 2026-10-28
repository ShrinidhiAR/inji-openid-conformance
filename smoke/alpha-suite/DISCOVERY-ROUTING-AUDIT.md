# Issuer identifier and deployment discovery audit

Local source audit, 2026-10-28. Last real suite run40632837918 executes both
selected modules, each INTERRUPTED/FAILED at VCIGetDynamicCredentialIssuerMetadata.
No HTTP status/cause retained from that condition, so actual404is unconfirmed.

## Contract and consistency

| Value | Source contract | Configured value |
|---|---|---|
| Issuer identifier | CredentialConfigurationServiceImpl credentialIssuer from mosip.certify.domain.url; metadata.credential_issuer same | https://certify.local.test:8443 |
| Official issuer metadata URL | pinned suite VCIGetDynamicCredentialIssuerMetadata.extractMetadataEndpointUrl prepends /.well-known/openid-credential-issuer to issuer path | https://certify.local.test:8443/.well-known/openid-credential-issuer |
| Native Certify metadata handler | WellKnownController + spring.mvc.servlet.path=/v1/certify | /v1/certify/.well-known/openid-credential-issuer |
| Official alpha deployment exposure | Helm values.yaml437-439 exact root metadata URI rewrite to native handler | Missing from new TLS gateway, existed in stage4 HTTP gateway |
| Credential endpoint | credentialIssuer + servletPath + /issuance/credential | https://certify.local.test:8443/v1/certify/issuance/credential |
| Nonce endpoint | credentialIssuer + servletPath + /nonce | https://certify.local.test:8443/v1/certify/nonce |
| Proof JWT aud | JwtProofValidator credentialIdentifier from mosip.certify.identifier=${mosip.certify.domain.url} | Same Certify origin, no path |
| AS identifier | eSignet discovery.issuer-id=${mosip.esignet.domain.url}; token.iss same source | https://esignet.local.test:8443 |
| AS OAuth discovery | Existing esignet-gateway exact root /.well-known/oauth-authorization-server to native /v1/esignet/oauth/.well-known/oauth-authorization-server | Existing AS gateway retained, unlike Certify bypass |
| Credential access-token aud | TokenServiceImpl scopesResourceMapping[sample_vc_mdoc], Certify authn.allowed-audiences identical | ASorigin/v1/esignet/vci/credential |
| MDOC credential issuer trust | Separate TESTIACA/DS and certificate fields | No change proposed |

Changing the Certify issuer to append /v1/certify is not a correct workaround:
metadata endpoint builders would double /v1/certify and proof audience would
change. The origin-only advertised issuer and endpoint values are coherent.
The alpha deployment exposes root discovery separately. Missing reverse-proxy
exposure in this new harness is established by source comparison. This is not
an established product metadata defect or proven runtime404.

## Local candidate correction

Restore ONLY exact `/.well-known/openid-credential-issuer` to
`http://certify-app:8090/v1/certify/.well-known/openid-credential-issuer` inside
Certify TLSserver, matching official alpha Helm and prior stage4 gateway.
No wildcard rewrites, redirect, invented metadata, content mutation, identifier
change, new audience or scheme changes. Otherpaths pass unchanged. Same Host
and X-Forwarded-Proto headers as existing TLS gateway.

Local generated config asserts exactly1such rule; strict allcertificate/SAN
and request-contract regressions22tests pass. Local nginx binary/container is
not available, so actual nginx parser/routing not executed here. No push/run.

## Diagnostics prepared locally

Official event projection only for VCIGetDynamicCredentialIssuerMetadata:
source target equals controlled expected URL -> emit origin label certify and
fixed expected path; mismatches bool only, never arbitrary URL/query. Integer
HTTP100..599if logged. Error_class/cause_class only exact transport/TLS/HTTP
allowlist, no message/stack/config/header/body. Exact HttpClientErrorException
$NotFound class yields not_found category, not fabricated integer status.
Unit test confirms injected secrets/arbitrary URL/classes absent. New file
metadata-fetch-evidence.jsonl is explicit upload/audit allowlist only.

Remaining uncertainty: last runtime exact cause not recoverable; new exposure
may allow suite checks to run or reveal further actual product/protocol findings.
Preserve native report (2failed, duplicate summary link and clippedwideassertion)
unmodified. No polish while diagnosing actual flow.

## Source URLs

https://raw.githubusercontent.com/inji/inji-certify/8fdf71656979a72fa8263766d4dec3cc25127b76/helm/inji-certify/values.yaml
https://raw.githubusercontent.com/inji/inji-certify/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-service/src/main/java/io/mosip/certify/services/CredentialConfigurationServiceImpl.java
https://gitlab.com/openid/conformance-suite/-/raw/23353b36957d6466010de767c812d2c91ed37638/src/main/java/net/openid/conformance/vci10issuer/condition/VCIGetDynamicCredentialIssuerMetadata.java
