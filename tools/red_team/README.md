# Red team harness

The purpose of this repository is to make audit failures **measurable**.

This folder contains a small harness that intentionally simulates vendor control-plane
dependencies, so the test suite can prove it detects them.

Two dependency classes are modeled:

- **License server**: a runtime that must contact a remote endpoint to execute.
- **Scheduler endpoint**: a runtime that queries an orchestration control plane to run.

The reference runtime supports this harness via two environment variables:

- `AI_AUDIT_VENDOR_LICENSE_URL`
- `AI_AUDIT_SCHEDULER_URL`

When either is set, the runtime performs a simple HTTP GET and logs an `external_dependency`
event into `provenance/provenance.log.jsonl`.

The audit suite then fails vendor independence checks by scanning the replay bundle for
forbidden hints (URLs, license/scheduler strings, registry domains, etc.).

This is intentional. The tests prove that "it ran" is not the same as "it is auditable".

## Why this matters

Vendor control planes are often framed as "operational details".
In regulated or safety-critical settings they are part of the correctness boundary:

- If a license server goes away, the system stops being verifiable.
- If a scheduler endpoint changes policy, the execution record changes.
- If the control plane is proprietary, audit collapses into attestation.

The harness is here so reviewers can see that failure mode in code.
