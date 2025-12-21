#!/usr/bin/env bash
set -euo pipefail

# Demonstrate reference implementation replay does not depend on scheduler availability.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCEN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCEN_DIR/reference_impl_passes.log"

python - <<'PY' >"$LOG" 2>&1
import os, tempfile, zipfile
from reference_impl.axm_runtime import run
from tools.pack_replay_bundle import main as pack
from tools.replay import main as replay
from tools.verify import main as verify

tmp = tempfile.mkdtemp(prefix="ai_exec_audit_example_")
out1 = os.path.join(tmp, "orig")
out2 = os.path.join(tmp, "replay")

run(ir_path=os.path.join("ir", "demo_ir.json"), user_input="Test input", out_dir=out1, provenance_path=os.path.join("provenance", "provenance.log.jsonl"))
bundle = pack(out1)

extract = os.path.join(tmp, "bundle")
os.makedirs(extract, exist_ok=True)
with zipfile.ZipFile(bundle, "r") as z:
    z.extractall(extract)

replay(extract, out2)

v1 = verify(out1)
v2 = verify(out2)

if v1["decision_record_sha256"] == v2["decision_record_sha256"]:
    print("OK: replay succeeded offline using artifacts only; verify_report status=ok")
else:
    print("FAIL: mismatch")
PY

echo "Wrote: $LOG"
