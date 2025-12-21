# Scenario: scheduler unavailable

## What breaks

Many production deployments assume an always-available orchestration layer (e.g., a cluster scheduler).
When that layer is unavailable, *replay and audit often fail* because the execution context cannot be reconstructed.

This folder contains an illustrative failure log and the required audit behavior.

### Typical stack behavior

See `typical_stack_behavior.log`.

### Audit requirement

Even when the scheduler is unavailable, the system must be able to:
- reconstruct what executed from local artifacts
- reproduce the decision record (offline replay)
- verify hashes

### Reference implementation

See `reference_impl_passes.log` and run the tests at repo root.
