# Denied Communications Authority Rehearsal

This directory contains the neutral, loopback-only interactive host for the standards-first mating surface. It is organized as an acceptance and rehearsal station rather than a tactical C2 product interface.

## User workflow

```text
Plan
  select a source-controlled qualified scenario
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
Evaluator disposition
  preserve the automatic result
  issue one separate accept, reject, or defer receipt
        ↓
Evidence
  inspect source and artifact custody
  export the session, verification, disposition, and combined package
  inspect separately admitted external-evidence receipts
```

Guide remains available at any time and links to role-based support documentation under `docs/`. The separate evaluator workspace is served at `/evaluator.html`.

## Execution boundary

The browser contains presentation and local API calls. Scenario definitions, procedures, checks, expected-versus-observed evaluation, signature generation, and evaluator-disposition checks are source-controlled and executed server-side. The browser does not implement authority, lease, replay, partition, reconciliation, C2SIM semantic, automatic acceptance, or disposition-signature decisions.

The Node host directly imports:

```text
mating_surface/semantic/authority_sidecar.mjs
mating_surface/semantic/run_semantic_rehearsal.mjs
mating_surface/test_hosts/core/fault_machine.mjs
mating_surface/rehearsal_console/evaluator_disposition.mjs
```

The server owns bounded session execution, loads the content-addressed scenario catalog, computes the automatic evaluation, verifies session replay, issues immutable local evaluator dispositions, and returns receipts. The host binds only to loopback and mechanically refuses unrecognized Host, foreign Origin, cross-site fetch context, non-JSON state-changing requests, oversized requests, and path traversal.

## Scenario and automatic-evaluation ownership

`scenarios.mjs` is the canonical rehearsal acceptance catalog. Each definition binds its baseline configuration, ordered procedure, and checks. Exact runs may pass; unfinished runs remain incomplete; expectation mismatches fail; and configuration or procedure drift is retained as a non-accepting deviation. See `docs/SCENARIO_CATALOG_AND_ACCEPTANCE.md`.

## Evaluator disposition ownership

`evaluator_disposition.mjs` keeps human disposition separate from automatic evidence. An automatic `pass` may receive an `accept`, `reject`, or `defer` disposition. Automatic `fail`, `incomplete`, and `deviated` results cannot be converted into an accepted qualified result. The local Ed25519 key protects receipt integrity for the current host process but does not authenticate organizational identity or establish program acceptance authority. See `docs/EVALUATOR_DISPOSITION.md`.

## External evidence ownership

`external_evidence.mjs` validates detached evidence produced outside the canonical session runtime. The retained standing-orders artifact is digest-only: its private source bytes are not committed. The admission module derives bounded `fail` or `incomplete` results only and has no canonical-closure or acceptance authority. It refuses self-asserted catalog, definition, session, verification, or replay claims. A future closure path must be separately implemented, load and verify the cited canonical artifacts, call the canonical session verifier, and require the verified session itself to bind the exact external source evidence set.

The retained external result is deliberately `incomplete` and acceptance-ineligible. It establishes only that the presented synthetic allowlist mapping passed inside an admin-injected harness. See `docs/EXTERNAL_EVIDENCE_ADMISSION.md`.

## Qualified scenarios

- baseline partition, duplicate order, delayed report, and explicit supersession;
- local operator absent;
- offline lease expiry;
- total isolation;
- conflicting returning authority;
- returning authority absent;
- exported session replay;
- evaluator accept, reject, defer, tamper refusal, and immutable one-disposition custody.

The digest-only standing-orders receipt is not added to this scenario list because it was not executed by the canonical session runtime.

## Documentation

Start with `docs/README.md`. The set includes operator, user, conductor, evaluator, verifier, external-evidence, interface-design, test, accessibility, traceability, and version artifacts. The documents are DID-shaped working artifacts. They are not contractual data items unless a contract invokes and tailors them.

## Run from a source checkout

Rebuild the exact rehearsal evidence, then run:

```bash
node mating_surface/rehearsal_console/server.mjs \
  --evidence qualification/c2sim-public-reference \
  --host 127.0.0.1 \
  --port 8787
```

Open `http://127.0.0.1:8787`. Open `http://127.0.0.1:8787/evaluator.html` for the separate evaluator disposition.

Verify the detached external receipt with:

```bash
node --test mating_surface/rehearsal_console/conformance/external_evidence.test.mjs
```

## Claim boundary

The current evidence covers an unclassified public C2SIM reference artifact, deterministic local transport faults, canonical authority receipts, loopback interaction, detached replay, local evaluator-disposition integrity, and one private-source digest-only external-evidence qualification. The external receipt is automatically incomplete and acceptance-ineligible. It does not authenticate evaluator identity, establish contractual or program acceptance, qualify an operational C2SIM profile, field network, representative operator readiness, target hardware, external provider integration, or any command, targeting, engagement, effector, execution, or weapons capability.
