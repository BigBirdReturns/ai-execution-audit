# Standards-first mating surface

This directory is the canonical integration boundary for external command, control, sensing, simulation, and platform systems.

It is deliberately **not** an AXM user interface, a Polybolos interface, a vendor-neutral dashboard, or a renamed proprietary schema. It carries no dandelion branding and it does not ask a provider to adopt AXM vocabulary.

The surface is assembled from standards already used in the target venue. AXM remains behind the surface as the authority, partition, replay, evidence, and acceptance implementation. A provider remains behind its own edge adapter. Neither implementation is allowed to redefine the venue contract.

## Governing rule

```text
provider-native implementation
        ↓
provider edge adapter
        ↓
venue-standard port
        ↓
standards-first mating surface
        ↓
authority / partition / evidence sidecars
        ↓
venue-standard port
        ↓
receiving system
```

The canonical object is the **standard port**, not either vendor's private object model.

A provider adapter may translate a private representation into a registered standard only when it possesses the official schema, generated bindings, or an authorized profile for that standard. The mating surface binds the exact standard, revision, profile, validator, and payload digest. It does not recreate controlled standards from memory or infer missing semantics from product copy.

## Layers

### Mission and command semantics

Use the standard selected by the program and platform, including Open Mission Systems and Universal Command and Control Interface where applicable, or the applicable tactical-data-link message standard.

### Real-time data plane

Use OMG Data Distribution Service and RTPS profiles where the venue requires real-time publish/subscribe, explicit quality of service, resource limits, deadlines, and degraded-link behavior.

### Shared situational awareness

Use TAK and Cursor-on-Target profiles when that is the fielded common-operating-picture boundary. These observations never grant command authority by themselves.

### Joint tactical exchange

Use the applicable controlled MIL-STD-6016 Link 16 or MIL-STD-6017 Variable Message Format artifact. Payloads remain opaque to this repository unless the exact authorized standard artifact and validator are loaded.

### Presentation

Use MIL-STD-2525 for joint military symbology. AXM and provider branding do not become operational symbology.

### Simulation, rehearsal, and the cabinet

Use SISO C2SIM, MSDL, HLA, DIS, WebLVC, Gateway Description Language, and Gateway Filtering Language as appropriate. MAME and MotionDeck are test hosts that consume those standard scenario and gateway contracts. They are not military message standards and they never become the operational authority surface.

### Platform integration

Use the platform's required MOSA family, including OMS/UCI, CMOSS, FACE, or SOSA as applicable. A target platform selects the profile. The mating surface does not collapse those families into one invented universal schema.

## Authority and evidence

The authority-under-partition mechanism is a sidecar to the standard message, not a replacement for it. The sidecar binds:

- the exact standard message identity and payload digest;
- issuing authority and delegation;
- software and configuration identity;
- current communications profile and partition epoch;
- offline lease, expiry, refusal, and safe-state behavior;
- replay, reconciliation, and detached evidence.

The standard payload remains standard-shaped. The authority receipt remains independently verifiable. Neither is permitted to impersonate the other.

## Provider adapters

Provider-specific folders are leaf implementations. They may contain codecs, generated bindings, field maps, and negative fixtures. They may not become the canonical mating surface, add provider terms to a venue profile, invent a product UI, or require the rest of the estate to speak one vendor's private schema.

When a provider already emits a venue standard, the adapter should pass that standard object through with identity and validation rather than normalize it into an AXM-owned surrogate.

## Current state

The registry and reference venue profile are public metadata and conformance scaffolding. Controlled standards remain metadata-only until their authorized artifacts are supplied. Public simulation schemas may be vendored and verified independently in later lanes.

No operational command, targeting, engagement, effector control, weapons employment, or combat-effectiveness claim is made here.