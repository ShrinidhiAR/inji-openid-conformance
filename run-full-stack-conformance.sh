#!/bin/bash
# One-command orchestration: pinned native source -> compile -> source-built MinIO -> one owned
# synthetic Certify+Verify+suite stack -> selected happy-flow modules -> native TestNG reports + S3 -> cleanup.
# Same steps as .github/workflows/native-combined.yml. Scope is limited: selected happy flows only,
# not full plans, not certification. Unsupported selections fail closed.
set -euo pipefail
cd "$(dirname "$0")"
usage(){ echo "usage: $0 --combined --approve-runtime [--output DIR]   (--component certify|verify is not implemented: exit 2)" >&2; exit 2; }
mode=""; approve=0; out=combined-conformance-out
while [ $# -gt 0 ]; do
  case "$1" in
    --combined) mode=combined;;
    --component) [ $# -ge 2 ] || usage; echo "unsupported: single-component orchestration is not implemented; use --combined" >&2; exit 2;;
    --approve-runtime) approve=1;;
    --output) [ $# -ge 2 ] || usage; out="$2"; shift;;
    *) usage;;
  esac; shift
done
[ "$mode" = combined ] || usage
if [ "$approve" != 1 ]; then
  echo "refusing: this boots docker containers, edits the hosts file, and builds MinIO; pass --approve-runtime" >&2; exit 2
fi
work="${CONFORMANCE_WORK:-$(mktemp -d)}"; : "${JAVA_HOME:?JAVA_HOME (Java 21 or per workflow) required}"
for c in certify verify; do
  [ -d "$work/native-$c-upstream/.git" ] || git clone --no-checkout "https://github.com/inji/inji-$c" "$work/native-$c-upstream"
done
git -C "$work/native-certify-upstream" checkout --detach 8fdf71656979a72fa8263766d4dec3cc25127b76
git -C "$work/native-verify-upstream" checkout --detach 4c4289026968beb535d3dbdd500947152c43f708
for c in certify verify; do
  python3 rig-integration/stage_isolated.py --component "$c" --upstream "$work/native-$c-upstream" --destination "$work/native-$c-rig"
  mvn -q -f "$work/native-$c-rig/pom.xml" -DskipTests -Dgpg.skip=true -Dmaven.gitcommitid.skip=true compile dependency:build-classpath -Dmdep.outputFile="$work/native-$c-classpath"
done
python3 rig-integration/build_minio.py --output "$work/approved-minio"
python3 rig-integration/tests/minio_native_acceptance.py --binary "$work/approved-minio" --provenance "$work/approved-minio.provenance.json" --java "$JAVA_HOME/bin/java" \
  --certify-classpath "$work/native-certify-rig/target/classes:$(cat "$work/native-certify-classpath")" --verify-classpath "$work/native-verify-rig/target/classes:$(cat "$work/native-verify-classpath")"
mkdir -p "$work/owned"; status=0
python3 rig-integration/run_combined.py --output "$out" --locator "$work/owned/locator.json" --java-home "$JAVA_HOME" --minio-binary "$work/approved-minio" --minio-provenance "$work/approved-minio.provenance.json" \
  --certify-classpath "$work/native-certify-rig/target/classes:$(cat "$work/native-certify-classpath")" --verify-classpath "$work/native-verify-rig/target/classes:$(cat "$work/native-verify-classpath")" || status=$?
[ ! -f "$work/owned/locator.json" ] || python3 rig-integration/fallback_cleanup.py --locator "$work/owned/locator.json"
python3 rig-integration/audit_evidence.py "$out"
exit "$status"
