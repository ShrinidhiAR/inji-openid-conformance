#!/bin/bash
# One-command orchestration, and the single entrypoint the native-combined workflow calls (no second copy of the steps):
#   pinned native source -> compile -> source-built MinIO -> one owned synthetic stack -> selected happy-flow modules
#   -> native TestNG reports + S3 -> cleanup -> public evidence audit.
# Scope is limited: selected happy flows only, not full official plans, not certification.
#   --combined | --component certify | --component verify    which native rig(s) run (the same owned stack serves all)
#   --approve-runtime                                         required: boots docker, edits hosts, builds MinIO
#   --phase all|prepare|run|cleanup|audit                      default all; split phases need CONFORMANCE_WORK set
#   --output DIR                                              default combined-conformance-out
# Unsupported selections fail closed with exit 2.
set -euo pipefail
cd "$(dirname "$0")"
usage(){ echo "usage: $0 (--combined | --component certify|verify) --approve-runtime [--phase all|prepare|run|cleanup|audit] [--output DIR]" >&2; exit 2; }
mode=""; sel=""; approve=0; phase=all; out=combined-conformance-out
while [ $# -gt 0 ]; do
  case "$1" in
    --combined) [ -z "$mode" ] || usage; mode=1; sel=both;;
    --component) [ $# -ge 2 ] || usage; [ -z "$mode" ] || usage
      case "$2" in certify|verify) sel="$2"; mode=1;; *) echo "unsupported component: only certify or verify" >&2; exit 2;; esac; shift;;
    --approve-runtime) approve=1;;
    --phase) [ $# -ge 2 ] || usage
      case "$2" in all|prepare|run|cleanup|audit) phase="$2";; *) echo "unsupported phase" >&2; exit 2;; esac; shift;;
    --output) [ $# -ge 2 ] || usage; out="$2"; shift;;
    *) usage;;
  esac; shift
done
[ -n "$mode" ] || usage
if [ "$approve" != 1 ]; then
  echo "refusing: this boots docker containers, edits the hosts file, and builds MinIO; pass --approve-runtime" >&2; exit 2
fi
if [ "$phase" != all ] && [ -z "${CONFORMANCE_WORK:-}" ]; then echo "refusing: --phase $phase needs CONFORMANCE_WORK so phases share one work directory" >&2; exit 2; fi
case "$sel" in both) comps="certify verify";; *) comps="$sel";; esac
work="${CONFORMANCE_WORK:-$(mktemp -d)}"
# stage_isolated.py and fallback_cleanup.py only accept paths under the system temp dir; refuse early with a clear reason.
case "$(realpath -m "$work")" in /tmp/*) ;; *) echo "refusing: CONFORMANCE_WORK must be under /tmp (isolated staging and exact cleanup only accept /tmp paths)" >&2; exit 2;; esac
# mkdtemp/tempfile in the Python steps follow TMPDIR; fallback cleanup only accepts /tmp.
case "$(realpath -m "${TMPDIR:-/tmp}")" in /tmp|/tmp/*) ;; *) echo "refusing: TMPDIR must be under /tmp (isolated staging and exact cleanup only accept /tmp paths)" >&2; exit 2;; esac
mkdir -p "$work"
cp_arg(){ echo "$work/native-$1-rig/target/classes:$(cat "$work/native-$1-classpath")"; }
status=0
# Review-window settings and the repository token belong to the run phase only (run_combined pops the token before anything else starts).
# The prepare phase runs git, Maven, Go, MinIO and its acceptance test, so none of them may inherit these.
prepare(){ ( unset GITHUB_TOKEN CONFORMANCE_REVIEW_WINDOW CONFORMANCE_REVIEW_DIR; prepare_steps ); }
prepare_steps(){
  : "${JAVA_HOME:?JAVA_HOME (Java 21 or per workflow) required}"
  local c
  for c in $comps; do
    [ -d "$work/native-$c-upstream/.git" ] || git clone --no-checkout "https://github.com/inji/inji-$c" "$work/native-$c-upstream"
    case "$c" in certify) pin=8fdf71656979a72fa8263766d4dec3cc25127b76;; verify) pin=4c4289026968beb535d3dbdd500947152c43f708;; esac
    git -C "$work/native-$c-upstream" checkout --detach "$pin"
    python3 rig-integration/stage_isolated.py --component "$c" --upstream "$work/native-$c-upstream" --destination "$work/native-$c-rig"
    mvn -q -f "$work/native-$c-rig/pom.xml" -DskipTests -Dgpg.skip=true -Dmaven.gitcommitid.skip=true compile dependency:build-classpath -Dmdep.outputFile="$work/native-$c-classpath"
  done
  python3 rig-integration/build_minio.py --output "$work/approved-minio"
  local cps=(); for c in $comps; do cps+=("--$c-classpath" "$(cp_arg "$c")"); done
  python3 rig-integration/tests/minio_native_acceptance.py --binary "$work/approved-minio" --provenance "$work/approved-minio.provenance.json" --java "$JAVA_HOME/bin/java" "${cps[@]}"
}
child=""
run(){
  : "${JAVA_HOME:?JAVA_HOME required}"
  mkdir -p "$work/owned"
  local cps=(); local c; for c in $comps; do cps+=("--$c-classpath" "$(cp_arg "$c")"); done
  python3 rig-integration/run_combined.py --output "$out" --locator "$work/owned/locator.json" --java-home "$JAVA_HOME" --minio-binary "$work/approved-minio" --minio-provenance "$work/approved-minio.provenance.json" --component "$sel" "${cps[@]}" &
  child=$!
  wait "$child" || status=$?
  child=""
}
cleanup(){ [ ! -f "$work/owned/locator.json" ] || python3 rig-integration/fallback_cleanup.py --locator "$work/owned/locator.json" || status=2; }
audit(){ if [ -d "$out" ]; then python3 rig-integration/audit_evidence.py "$out" || status=2; else echo "no evidence directory to audit" >&2; status=2; fi; }
# A signal reaches the owned child first (run_combined has its own exact cleanup), then the script exits through its EXIT path.
on_signal(){
  if [ -n "$child" ]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi
  exit "$1"
}
trap 'on_signal 143' TERM
trap 'on_signal 130' INT
# Default one-command path: whatever happens (prepare failure, run failure, signal), clean up exactly what this run owns and audit
# whatever evidence exists. The original exit code is kept; cleanup or audit failures are reported and only change a zero exit.
finish(){
  local rc=$?; trap - EXIT TERM INT; set +e
  [ "$rc" != 0 ] || rc=$status
  local bad=0
  [ ! -f "$work/owned/locator.json" ] || python3 rig-integration/fallback_cleanup.py --locator "$work/owned/locator.json" || { echo "cleanup_failed" >&2; bad=1; }
  if [ -d "$out" ]; then python3 rig-integration/audit_evidence.py "$out" || { echo "audit_failed" >&2; bad=1; }; fi
  [ "$rc" != 0 ] || [ "$bad" = 0 ] || rc=2
  exit "$rc"
}
case "$phase" in
  prepare) prepare;;
  run) run;;
  cleanup) cleanup;;
  audit) audit;;
  all) trap finish EXIT; prepare; run;;
esac
exit "$status"
