#!/bin/sh
# Existing-environment runner. Does not provision or claim whole-stack execution.
set -eu
cd "$(dirname "$0")"
exec python3 scripts/conformance_runner.py "$@"
