# Prepared alpha direct issuance, not conformance evidence

Status: local preparation only. No alpha issuance has been run with this path.
Do not launch another run without the project owner's run approval.

The separate `alpha-direct` manual mode skips the suite, VP, 0.14 stack, and
readiness-only job. It starts the complete tagged alpha DB initializer and config
plus classic eSignet 1.8.0 on one disposable isolated network. The 0.14 baseline
is unchanged. Main is unchanged. There is no merge approval.

Deployment changes from tagged alpha:
- Existing readiness adjustment: first public health matcher is `/actuator/health`,
  not the tagged `**/actuator/**`. No metadata/nonce/config security exclusions.
- External auth URL and JWT issuer: `http://esignet:8088`.
- JWKS: `http://esignet:8088/v1/esignet/oauth/.well-known/jwks.json`.
- Allowed audience: exactly `http://esignet:8088/v1/esignet/vci/credential`,
  matching the classic credential-scope mapping. No permissive audience fallback.
- Fresh runtime P-256 TEST signer supplied as base64 PKCS8 DER + `||` + X509 DER.
  Private config directory is 0700, files 0600. Only public cert is evidence.
- No `local` alpha profile and no bypass of alpha token/proof validators.

One run scope:
1. Complete release DB initialization; stable UP and key-runner check.
2. Create/read back synthetic mDL configuration and verify Final metadata.
3. Seed fresh synthetic identity; register fresh in-memory wallet public key.
4. Classic auth-code flow, private_key_jwt exchange, independently verify access
   signature and exact issuer/audience/client/scope/time claims against eSignet JWKS.
5. POST alpha nonce immediately before one Final request:
   `credential_configuration_id` + `proofs.jwt[]`, public ES256 proof key.
6. Parse exactly one `credentials[].credential`; verify in memory, pin embedded
   signer cert to this run's independent public anchor, verify COSE signature,
   MSO type/times/holder key, and every issuer-item digest.
7. Stop on first failure. No automatic retry or next run. Always tear down,
   remove private config, and check containers/volumes/network are gone.

Allowlisted evidence: public TEST anchor, last-stage, summary/failure/cleanup JSON.
Never upload credentials, raw service logs, HTTP bodies, tokens, proofs, nonces,
authorization codes, client keys, private signer or expanded runtime config.
Alpha validator errors can echo nonce values, so raw logs are unsafe.

Local evidence (not runtime issuance): real published alpha DTO tests and
JwtProofValidator/Nimbus signature tests; synthetic parser/redaction/signer tests;
verifier regression using a privately held previously captured real 0.14 credential.
The extracted embedded anchor in that regression establishes self-consistency,
not independent issuer trust. Wrong fresh anchor and issuer-item tampering reject.

Known limitation: tagged alpha's access filter only recognizes `Bearer `. It
marks non-Bearer tokens inactive and issuance rejects inactive tokens. No alpha
DPoP acceptance was runtime-tested. Direct Bearer Final issuance can be tested
legitimately, but success cannot establish the official DPoP suite's conformance.
No security check is weakened to turn that limitation green.

Still requires approved runtime evidence: alpha/eSignet interoperability,
actual token claims, successful signer extraction, Final credential issuance,
and runtime negative-token/proof outcomes. Local Docker Compose rendering is
not available in the preparation environment; generated YAML structure and all
mounts/gates were inspected locally, not daemon-validated.

After approval, one manual workflow dispatch may run `mode=alpha-direct` on the
isolated experimental branch. Report the outcome and await direction afterward.
