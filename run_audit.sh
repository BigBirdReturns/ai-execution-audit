#!/usr/bin/env bash
set -euo pipefail

# One-command local run for the execution audit suite.
# Usage: ./run_audit.sh

python -m venv .venv >/dev/null 2>&1 || true
source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

pytest -q
