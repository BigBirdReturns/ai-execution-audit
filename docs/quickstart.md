# Quickstart

## Run the reference implementation and produce artifacts

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

python -m reference_impl.axm_runtime --ir ir/demo_ir.json --input "Refund request" --outdir out
python tools/pack_replay_bundle.py out
python tools/verify.py out
python tools/replay.py out
```

## Run the tests

```bash
pytest -q
```

## Generate a verdict artifact

```bash
python -m tools.audit_verdict .
cat artifacts/audit_verdict.json
```
