# AXM Polybolos congruent-shape adapter

This directory defines the **mating surface** between an external Polybolos implementation and the neutral AXM authority, evidence, partition, and reconciliation floor.

It does not implement, imitate, or replace Polybolos Command Intelligence, COMMAND CORE, HOTL, BELARX, its operator workflow, or its product interface. It also does not claim knowledge of Polybolos private structs, APIs, repositories, binaries, or deployment topology.

## Ownership boundary

Polybolos owns its observations, kinematics, tactical computations, resource logic, operator workflow, local persistence, product identity, and external platform integrations.

AXM owns the neutral candidate contract, evidence closure, external authority envelope, partition epoch, offline lease, replay protection, reconciliation, detached verification, and acceptance receipts.

The adapter owns only translation between those systems. A field is translated only when its mapping is explicit. Unknown information is either preserved under a declared policy, rejected, or recorded as a declared loss. It is never filled with a plausible substitute.

## Current state

The included reference shape is intentionally marked `provisional`. It exists only to exercise the conformance machinery. It is not represented as a Polybolos native schema. `live` mode refuses it until Mark or another authorized Polybolos maintainer supplies a representative fixture and confirms the mapping.

The conformance suite proves:

- provisional mappings cannot be promoted into live use;
- candidate data cannot self-authorize;
- mapped semantics are deterministic;
- exact round-trip promises are enforced;
- unmapped fields are visible through a stable digest and field ledger;
- declared losses remain attached to the translation receipt;
- AXM decisions return through a neutral status projection without inventing a Polybolos UI or internal state;
- unknown dispositions fail closed.

## Run

```bash
node --test adapters/polybolos/conformance/congruence.test.mjs
node adapters/polybolos/conformance/run_congruence.mjs qualification/polybolos-congruence/congruence-receipt.json
```

## Promotion gate

A real Polybolos adapter may move from `provisional` to `confirmed` only after the following artifacts exist:

1. A representative, authorized, non-sensitive external fixture or schema.
2. A named Polybolos maintainer who confirms each mapped semantic.
3. An explicit list of fields that are intentionally omitted, normalized, or irreversible.
4. Exact producer and build identity semantics.
5. A negative fixture proving candidate data cannot grant itself command authority.
6. A round-trip or one-way conformance determination for every mapped field.
7. A detached test showing the resulting neutral candidate enters the existing AXM checkpoint, authority, partition, replay, and reconciliation path.

Until those gates pass, the adapter is a fixture harness rather than an operational receiver.
