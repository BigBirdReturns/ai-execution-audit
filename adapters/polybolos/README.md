# Polybolos provider-edge adapter

This directory is **not** the mating surface.

The canonical mating surface is `mating_surface/`, where the program selects the operational standards already used by the target venue. Polybolos remains one external provider implementation behind those standard ports. AXM remains one authority, partition, evidence, replay, and acceptance implementation behind the same ports.

Neither provider owns the venue vocabulary.

## Correct boundary

```text
Polybolos native implementation
        ↓
Polybolos edge codec or gateway
        ↓
selected venue standard
        ↓
standards-first mating surface
        ↓
authority and evidence sidecars
```

When Polybolos already emits UCI, DDS, TAK/CoT, Link 16, VMF, C2SIM, HLA/DIS, or another program-selected standard, the adapter should preserve that standard object and bind its exact artifact, revision, message identity, and payload digest. It should not normalize the message into an AXM-owned substitute.

When a private Polybolos representation must be translated, the translation is a leaf gateway. It must be described by the applicable gateway and filter artifacts, declare every loss and irreversible transformation, and terminate at a registered standard port. Private field names remain local to the adapter.

## Status of the existing congruence work

The mapping, structural-profile, and signed-admission machinery in this directory is retained as a **proprietary-deviation quarantine harness**. It is useful only when a provider cannot directly emit a selected venue standard.

It is not required merely because Polybolos exists, and it is not the default integration path.

A private-shape map may not:

- become canonical venue vocabulary;
- require the rest of the estate to speak Polybolos terms;
- define an operational user interface;
- imitate Polybolos Command Intelligence, COMMAND CORE, HOTL, or BELARX;
- replace official UCI, DDS, TAK/CoT, Link 16, VMF, C2SIM, MSDL, HLA, DIS, CMOSS, FACE, or other selected program artifacts;
- grant candidate data command authority.

## Preferred integration order

1. Exact standard pass-through.
2. Official generated binding or codec.
3. Program-approved standard profile.
4. Loss-accounted gateway described against the standard.
5. Proprietary shape mapping only for the irreducible residue.

## Live promotion

A live provider adapter requires the exact target standard artifact and a conformance transaction against the selected venue profile. Confirmation of a private provider shape alone is insufficient.

No operational command, targeting, engagement, effector control, weapons employment, or combat-effectiveness claim is made here.