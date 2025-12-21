# Scenario: runtime upgrade drift

## What breaks

Even if weights are unchanged, changing the runtime (driver, kernel, compiler, or inference engine) can change outputs.
If the deployment cannot prove *what runtime executed*, external audit becomes impossible.

This folder shows the failure mode as a concept:
- baseline decision record hash
- upgraded runtime decision record hash differs
- without pinned runtime fingerprints, the system cannot explain the change

## Why this matters

Regulated systems require:
- reproducibility
- traceability
- ability to re-audit decisions after the fact

If runtime drift is silent, compliance becomes non-verifiable.
