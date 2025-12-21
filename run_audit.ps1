# One-command local run for the execution audit suite.
# Usage: powershell -ExecutionPolicy Bypass -File .\run_audit.ps1

python -m venv .venv | Out-Null
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt | Out-Null

pytest -q
