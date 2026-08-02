# C2SIM semantic rehearsal

This lane advances the admitted public C2SIM reference artifact from structural custody and payload-opaque transport testing to a minimal schema-valid conversation. It remains simulation and rehearsal material.

The compiler generates four deterministic C2SIM XML messages directly against the exact admitted XSD:

```text
SubmitInitialization
→ ObjectInitialization
→ Order
→ TaskStatus report
```

The XML remains unchanged throughout the rest of the transaction. External receipts bind its message identity, payload digest, artifact admission, catalog, communications profile, partition epoch, authority decision, receiver replay disposition, and reconciliation result.

## Boundary

The semantic lane does not implement Polybolos, AXM, a command dashboard, or an operational coalition profile. It does not add private fields to C2SIM. The public OpenC2SIM artifact remains a reference implementation snapshot admitted only for test and rehearsal.

```text
schema-valid C2SIM XML
        ↓
semantic receipt
        ↓
message-bound authority sidecar
        ↓
payload-opaque transport fault machine
        ↓
receiver replay control
        ↓
explicit reconciliation
        ↓
read-only test-host frame
```

The first deterministic scenario sends initialization while connected, loses the headquarters link, issues one order and one task-status report inside a bounded offline lease, duplicates the order in transport, delays the report, restores the link, refuses the duplicate order at the receiver, and closes the partition through explicit authority supersession.

## Qualification

```bash
python -m unittest mating_surface.semantic.conformance.test_c2sim_semantic -v
node --test mating_surface/semantic/conformance/*.test.mjs

python mating_surface/semantic/c2sim_semantic.py \
  upstream-c2sim/C2SIM_SMX_LOX_V1.0.1.xsd \
  qualification/c2sim-public-reference/artifact-transaction.json \
  qualification/c2sim-public-reference/xsd11-catalog.json \
  qualification/c2sim-public-reference/semantic-conversation

node mating_surface/semantic/run_semantic_rehearsal.mjs \
  qualification/c2sim-public-reference/semantic-conversation \
  qualification/c2sim-public-reference/artifact-transaction.json \
  qualification/c2sim-public-reference/xsd11-catalog.json \
  qualification/c2sim-public-reference/semantic-rehearsal

node mating_surface/semantic/verify_semantic_rehearsal.mjs \
  qualification/c2sim-public-reference/semantic-conversation \
  qualification/c2sim-public-reference/semantic-rehearsal \
  qualification/c2sim-public-reference/semantic-rehearsal-verification.json
```

The resulting `standards-semantic-rehearsal-frame/1` is the sole cabinet-facing object. MAME and MotionDeck may consume it as read-only state. They do not receive XML payloads, authority mutation, targeting, engagement, effector, or execution capabilities.
