# Denied Communications Authority Rehearsal

This directory contains the neutral, loopback-only interactive host for the standards-first mating surface. It is organized as an acceptance and rehearsal station rather than a tactical C2 product interface.

## User workflow

```text
Plan
  select a qualified scenario
  review objective, expected result, and pass condition
  record initial conditions
        ↓
Run
  follow the bounded runbook
  observe run, communications, and authority state separately
  retain persistent action feedback and recovery
        ↓
Evaluate
  compare expected and observed behavior
  replay the exported session through the same runtime
        ↓
Evidence
  inspect source and artifact custody
  export the exact session receipt
```

Guide remains available at any time and links to role-based support documentation under `docs/`.

## Execution boundary

The browser contains presentation, test-plan metadata, expected-versus-observed comparison, and local API calls. It does not implement authority, lease, replay, partition, reconciliation, or C2SIM semantic decisions.

The Node host directly imports:

```text
mating_surface/semantic/authority_sidecar.mjs
mating_surface/semantic/run_semantic_rehearsal.mjs
mating_surface/test_hosts/core/fault_machine.mjs
```

The server owns bounded session execution and returns receipts. The host binds only to loopback and mechanically refuses unrecognized Host, foreign Origin, cross-site fetch context, non-JSON state-changing requests, oversized requests, and path traversal.

## Qualified scenarios

- baseline partition, duplicate order, delayed report, and explicit supersession;
- local operator absent;
- offline lease expiry;
- total isolation;
- conflicting returning authority;
- returning authority absent;
- exported session replay.

## Documentation

Start with `docs/README.md`. The set includes operator, user, conductor, verifier, interface-design, test, accessibility, traceability, and version artifacts. The documents are DID-shaped working artifacts. They are not contractual data items unless a contract invokes and tailors them.

## Run from a source checkout

Rebuild the exact rehearsal evidence, then run:

```bash
node mating_surface/rehearsal_console/server.mjs \
  --evidence qualification/c2sim-public-reference \
  --host 127.0.0.1 \
  --port 8787
```

Open `http://127.0.0.1:8787`.

## Claim boundary

The current evidence covers an unclassified public C2SIM reference artifact, deterministic local transport faults, canonical authority receipts, loopback interaction, and detached replay. It does not establish an operational C2SIM profile, field network, representative operator readiness, target-hardware qualification, external provider integration, or any command, targeting, engagement, effector, execution, or weapons capability.
