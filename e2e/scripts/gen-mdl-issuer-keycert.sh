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
# base64 can contain '/' and the value contains '||' itself; python avoids sed
# delimiter collisions entirely.
python3 - "$VALUE" <<'PYEOF'
import sys
value = sys.argv[1]
path = "config/certify-mock-mdl.properties"
lines = open(path).read().splitlines(True)
with open(path, "w") as f:
    for line in lines:
        if line.startswith("mosip.certify.mock.mdoc.issuer-key-cert="):
            f.write(f"mosip.certify.mock.mdoc.issuer-key-cert={value}\n")
        else:
            f.write(line)
PYEOF
# export the PEM for the suite's mdoc trust-anchor config
openssl x509 -in "$TMP/cert.der" -inform DER -out config/mdl-issuer-trust-anchor.pem
rm -rf "$TMP"
echo "patched issuer-key-cert into config/certify-mock-mdl.properties"
