#!/usr/bin/env bash
set -euo pipefail

# Simulated vendor stack behavior: requires a scheduler endpoint that may not exist.
# This script intentionally does NOT start the fake scheduler server.

OUTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$OUTDIR/typical_stack_behavior.log"

SCHED_URL="http://127.0.0.1:59999/scheduler"

python - <<PY >"$LOG" 2>&1 || true
import requests
url = "${SCHED_URL}"
try:
    requests.get(url, timeout=0.5)
    print("UNEXPECTED: scheduler reachable")
except Exception:
    print("ERROR: cannot reproduce run: scheduler unavailable (no job metadata, no container image digest, no runtime trace)")
PY

echo "Wrote: $LOG"
