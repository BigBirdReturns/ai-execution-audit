# Standards-port test hosts

This directory is the replaceable, read-only test-host boundary for the standards-first mating surface. It turns exact admitted artifacts into deterministic transport-fault evidence without implementing the standard's domain semantics. MAME, MotionDeck, a CLI, or another simulator may consume the retained frame, but no dashboard or live service belongs to the audit boundary.

## Fault machine

`core/fault_machine.mjs` accepts opaque synthetic payloads only after each payload has been bound to one admitted artifact, one artifact-use receipt, one structural catalog, one venue profile, and one standard port. The packet and payload sets must exactly match the scenario's send events. Extra packets, extra payloads, provider fields, and operational artifact use are refused.

A scenario can exercise pass-through delivery, explicit drop, deterministic duplication, deterministic delay, communications partition, bounded buffering, queue-capacity refusal, reconnect, FIFO recovery, and deliberately incomplete runs. A `drop` partition policy must use zero queue capacity, and link events must change state rather than recording no-op churn.

Each logical step applies its scenario event first. A reconnect then flushes the bounded FIFO queue. Due delayed packets are released after that event work. The run records this phase rule as `apply_event_then_release_due`, and conformance tests verify the same-step ordering.

## Receipt chain

```text
admitted standard artifact
        ↓
artifact use receipt
        ↓
XSD 1.1 structural catalog
        ↓
opaque test packet and payload digest
        ↓
scenario digest and deterministic fault schedule
        ↓
delivery / drop / buffer / delay journal
        ↓
detached run verification
        ↓
read-only standards-port test frame
        ↓
replaceable test host
```

The run identity binds the executable scenario digest, exact packet set, queue policy, event phase, deliveries, drops, unresolved delayed or buffered packets, metrics, and journal root. `core/fault_verifier.mjs` reconstructs the journal chain, link transitions, FIFO queue, delayed-release schedule, delivery and drop closure, packet outcomes, metrics, run identity, and frame identity without access to payload bytes.

The frame contains only identities, bounded state, metrics, the journal root, and the last journal event. It contains no payload bytes, provider product interface, command authority, targeting, engagement, effector, execution, dashboard, or live-service surface.

## Qualification

```bash
node --test mating_surface/test_hosts/conformance/fault_machine.test.mjs

node mating_surface/test_hosts/run_fault_machine_e2e.mjs \
  qualification/c2sim-public-reference/artifact-transaction.json \
  qualification/c2sim-public-reference/xsd11-catalog.json \
  qualification/c2sim-public-reference/standard-port-fault-machine

node mating_surface/test_hosts/core/fault_verifier.mjs \
  qualification/c2sim-public-reference/standard-port-fault-machine/fault-run.json \
  qualification/c2sim-public-reference/standard-port-fault-machine/test-frame.json \
  qualification/c2sim-public-reference/standard-port-fault-machine/verification-cli.json
```

The current C2SIM lane deliberately uses `opaque_transport_fixture` payloads. It does not claim that a C2SIM message instance was constructed or schema-validated, that the public reference artifact is an official operational distribution, or that the measured behavior represents a fielded network.
