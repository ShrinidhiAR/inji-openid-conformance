#!/usr/bin/env python3
"""Alpha smoke: read issuer metadata fail-closed.

Usage: read_issuer_metadata.py <metadata-json-file>
Exit 0 only if the file is valid JSON AND carries no MOSIP error envelope
(HTTP 200 with errors[] is NOT healthy metadata - fail closed on it).
Prints the protocol-surface facts the smoke reports on.
"""
import json, sys

def main() -> int:
    if len(sys.argv) != 2:
        print("::error::usage: read_issuer_metadata.py <file>")
        return 2
    try:
        with open(sys.argv[1]) as fh:
            raw = fh.read()
    except OSError as e:
        print(f"::error::cannot read metadata file: {e}")
        return 2
    if not raw.strip():
        print("::error::metadata response body is empty")
        return 1
    try:
        m = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"::error::metadata is not valid JSON: {e}")
        return 1
    if not isinstance(m, dict):
        print("::error::metadata is not a JSON object")
        return 1
    # MOSIP services return HTTP 200 with error envelopes - never trust status
    if m.get("errors"):
        print(f"::error::metadata endpoint returned an error envelope: "
              f"{[e.get('errorCode') for e in m['errors']]}")
        return 1
    if "response" in m and "credential_issuer" not in m and "credential_configurations_supported" not in m and "credentials_supported" not in m:
        # MOSIP envelope without errors but wrapped payload - unwrap
        m = m["response"] or {}
    final = "credential_configurations_supported" in m
    draft = "credentials_supported" in m
    print(f"credential_configurations_supported (1.0 Final): {final}")
    print(f"credentials_supported (draft-11): {draft}")
    print(f"nonce_endpoint: {m.get('nonce_endpoint', 'ABSENT')}")
    print(f"dpop_signing_alg_values_supported: {m.get('dpop_signing_alg_values_supported', 'ABSENT')}")
    print(f"credential_endpoint: {m.get('credential_endpoint', 'ABSENT')}")
    if not (final or draft):
        print("::error::metadata carries neither 1.0-Final nor draft-11 config field")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
