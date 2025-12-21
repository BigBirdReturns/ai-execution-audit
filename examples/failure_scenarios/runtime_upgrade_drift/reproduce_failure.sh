#!/usr/bin/env bash
set -euo pipefail

# Demonstrate a common drift pattern:
# the "same" logical workload produces different signed/hashed artifacts after a runtime upgrade.

SCEN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d -t ai_exec_audit_drift_XXXXXX)"

run_once() {
  local ver="$1"
  local outdir="$2"
  AI_AUDIT_RUNTIME_VERSION_OVERRIDE="$ver" \
    python -m reference_impl.axm_runtime --ir ir/demo_ir.json --input "Test input" --outdir "$outdir" >/dev/null
  python -m tools.verify "$outdir" | python -c "import sys, json; print(json.load(sys.stdin)['decision_record_sha256'])"
}

mkdir -p "$TMP/baseline" "$TMP/upgraded"
H1=$(run_once "0.1.0" "$TMP/baseline")
H2=$(run_once "0.2.0" "$TMP/upgraded")

{
  echo "baseline decision_record_sha256=$H1"
  echo "upgraded  decision_record_sha256=$H2"
  if [ "$H1" != "$H2" ]; then
    echo "DRIFT: artifacts differ across runtime versions"
  else
    echo "NO DRIFT: hashes equal (unexpected for this scenario)"
  fi
} > "$SCEN_DIR/analysis.md"

cp "$SCEN_DIR/analysis.md" "$SCEN_DIR/baseline.log"
cp "$SCEN_DIR/analysis.md" "$SCEN_DIR/upgraded_runtime.log"

echo "Wrote: $SCEN_DIR/analysis.md"
