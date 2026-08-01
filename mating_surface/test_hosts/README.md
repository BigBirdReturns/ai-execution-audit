# Standards-port test hosts

This directory turns admitted venue-standard artifacts into deterministic transport and interoperability test fuel.

A test host is not part of the operational standard. It receives a read-only frame after the standards-port transaction has been compiled and executed. MAME, MotionDeck, a browser, a CLI, or another simulator may consume the same frame without becoming the source of domain semantics or authority.

## Current fault machine

`core/fault_machine.mjs` operates on opaque test packets bound to:

- one admitted standards artifact;
- one artifact use receipt;
- one deterministic schema catalog;
- one venue profile and port;
- exact payload digests and byte counts.

The machine can exercise:

- pass-through delivery;
- explicit drop;
- deterministic duplication;
- deterministic delay and reordering;
- communications partition;
- bounded buffering;
- queue-capacity refusal;
- reconnect and FIFO recovery;
- incomplete runs with visible delayed or buffered residue.

The machine never interprets the payload. The first C2SIM lane uses opaque synthetic bytes and labels them `opaque_transport_fixture`. They are not represented as schema-valid C2SIM messages.

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
deterministic fault scenario
        ↓
delivery / drop / buffer / delay journal
        ↓
read-only standards-port test frame
        ↓
replaceable test host
```

The frame contains counts, state, identities, and the journal root. It contains no payload bytes, provider product interface, command authority, targeting, engagement, effector, or execution surface.

## Run

```bash
node --test mating_surface/test_hosts/conformance/fault_machine.test.mjs

node mating_surface/test_hosts/run_fault_machine_e2e.mjs \
  qualification/c2sim-public-reference/artifact-transaction.json \
  qualification/c2sim-public-reference/xsd11-catalog.json \
  qualification/standard-port-fault-machine
```

## Next host boundary

A MAME or MotionDeck adapter should read `standards-port-test-frame/1` and expose controls that compile into `standards-port-fault-scenario/1`. The adapter must not inspect or mutate standard payloads, invent military message semantics, reset authority, or convert the test host into an operational command path.
