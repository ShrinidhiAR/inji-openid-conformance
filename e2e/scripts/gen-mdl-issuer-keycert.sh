#!/usr/bin/env bash
# Generates the mock-mDL issuer key+certificate that the MDocMockVCIssuancePlugin
# requires as "base64(PKCS8 DER EC private key)||base64(X509 DER cert)" and
# patches it into certify-mock-mdl.properties. Self-signed is fine: the e2e
# suite config pins the same cert as the mdoc trust anchor.
set -euo pipefail
cd "$(dirname "$0")/../compose/certify"
TMP="$(mktemp -d)"
openssl ecparam -name prime256v1 -genkey -noout -out "$TMP/key.pem"
openssl pkcs8 -topk8 -nocrypt -in "$TMP/key.pem" -outform DER -out "$TMP/key.der"
openssl req -new -x509 -key "$TMP/key.pem" -outform DER -out "$TMP/cert.der" \
  -days 365 -subj "/CN=e2e-mDL-issuer"
VALUE="$(base64 -w0 "$TMP/key.der")||$(base64 -w0 "$TMP/cert.der")"
sed -i "s|^mosip.certify.mock.mdoc.issuer-key-cert=.*|mosip.certify.mock.mdoc.issuer-key-cert=${VALUE}|" \
  config/certify-mock-mdl.properties
# export the PEM for the suite's mdoc trust-anchor config
openssl x509 -in "$TMP/cert.der" -inform DER -out config/mdl-issuer-trust-anchor.pem
rm -rf "$TMP"
echo "patched issuer-key-cert into config/certify-mock-mdl.properties"
