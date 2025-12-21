# Extending this repository

This repository ships one reference runtime that passes the tests.
To evaluate another runtime, add an adapter that produces the same artifact set.

## Design rule

Do not change the tests to match your runtime.
Change your runtime adapter to match the artifact contract.

## Minimal adapter checklist

Your adapter should be able to:

1. Execute a workload using inputs from `ir/` (or your own deterministic inputs)
2. Emit an append only provenance ledger in `provenance/`
3. Pack a replay bundle zip in `artifacts/`
4. Produce a hash verification report

## Artifact contract

The tests assume three things exist after a run:

- A replay bundle zip that contains all replay inputs and pinned artifacts
- A provenance ledger with stable event records
- A verification report that confirms artifact hashes

See:
- `docs/provenance_schema.json`
- `tools/pack_replay_bundle.py`
- `tools/verify.py`
- `tools/replay.py`

## Suggested structure

Create a new folder:

- `adapters/<your_runtime>/run.py`

Implement a `run(ir_path, user_input, outdir)` function that produces the artifacts.
Then point the tests at your adapter via an environment variable or fixture.
