# Runtime adapters

The audit suite focuses on properties, not vendor claims.

Adapters provide a small contract for wrapping real execution stacks and emitting artifacts
in the same structure as the reference implementation.

## Contract

An adapter should produce:
- artifacts/input_bundle.json
- artifacts/decision_record.json
- provenance/provenance.log.jsonl
- ir/demo_ir.json (or a copy of the IR that was executed)

## Why adapters exist

Many AI stacks fail audit because:
- scheduler policy and priority decisions are opaque
- license gates enforce control-plane attestation
- adaptive runtimes make replay non-reconstructable

Adapters let the same tests evaluate:
- SLURM jobs
- containerized runtimes
- vendor SDK executions

See runtimes/*_stub.py for templates.
