# Audit requirements

This repository defines minimum execution audit requirements and provides tests that enforce them.

These tests are intentionally narrow.
They are not benchmarks.
They measure auditability properties, not task performance.

## Test 1: Offline replay

**Requirement**
The system must reproduce decisions with no network access and no external services.

**Pass criteria**
- Execution completes with networking disabled
- Decision outputs match the original run under the same artifacts
- No calls to external schedulers, telemetry, or APIs

**Common failure modes**
- "Cannot reach scheduler"
- "License server unavailable"
- "Telemetry required to proceed"
- "Remote model weights not cached"

## Test 2: Audit reconstruction from artifacts alone

**Requirement**
An auditor must be able to reconstruct what executed using only a replay bundle.

**Pass criteria**
- Replay bundle contains all required inputs and pinned artifacts
- A verifier can hash check artifacts and produce a report
- Replay produces the same decision record as the original run

**Common failure modes**
- Runtime depends on a remote registry or artifact store
- Execution metadata lives only in a vendor dashboard
- The bundle includes pointers instead of content

## Test 3: Bounded determinism

**Requirement**
Given the same inputs and pinned artifacts, the system must produce identical decision records.

**Pass criteria**
- Stable output hashes across repeated runs
- Determinism scope is explicitly stated and enforced
- Any permitted nondeterminism is bounded and logged

**Common failure modes**
- Adaptive kernels that change over time
- Unpinned dependencies
- Scheduler driven variability that changes execution order

## Test 4: Vendor independence

**Requirement**
The system must remain executable and auditable after vendor support ends or access is severed.

**Pass criteria**
- No dependency on vendor hosted services
- No required license checks that can be revoked remotely
- Audit artifacts remain sufficient for replay and verification

**Common failure modes**
- Token gated observability
- Remote policy enforcement
- Version pinning that requires private package registries
