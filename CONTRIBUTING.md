# Contributing

This repository focuses on one thing: making execution auditability testable.

## What to contribute

- New failure scenarios with minimal repro artifacts
- Runtime adapters that emit the same artifact set as the reference implementation
- Tests that tighten auditability requirements without adding assumptions

## What not to contribute

- Benchmark claims
- Vendor specific glue unless it is isolated in an adapter folder
- New dependencies unless they are strictly necessary

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Style

- Prefer simple, explicit code over frameworks.
- Keep artifacts small and readable.
- Avoid any text that depends on insider context.
