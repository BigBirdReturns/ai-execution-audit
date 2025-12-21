#!/usr/bin/env bash
set -euo pipefail
python -m reference_impl.axm_runtime --ir ir/demo_ir.json --input "Test input" --outdir out_demo_example > /dev/null
python -m tools.pack_replay_bundle out_demo_example > /dev/null
python -m tools.verify out_demo_example > /dev/null
echo "OK: replay succeeded offline using artifacts only; verify_report status=ok"
