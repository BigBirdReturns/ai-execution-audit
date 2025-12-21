# Threat model (audit focused)

This is not a security threat model for an AI model.
It is a threat model for execution auditability.

## Threats this repository targets

- Hidden control plane decisions (who ran what, when, with what policy)
- Undocumented runtime changes (kernel swaps, compiler drift, silent upgrades)
- Remote dependencies (license servers, registries, telemetry gates)
- Artifact substitution (a dashboard asserts a run that cannot be replayed)

## Non goals

- Preventing adversarial ML attacks
- Detecting data poisoning
- Measuring task accuracy

Those are important, but they are separate problems.

## Audit invariants

An external auditor should be able to:
- verify artifact integrity using hashes
- replay a run offline
- reconstruct the decision record
- detect drift when artifacts change
