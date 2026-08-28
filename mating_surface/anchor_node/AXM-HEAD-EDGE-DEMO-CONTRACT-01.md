# AXM HEAD Edge Demo Contract 01

## Object

This increment defines the first executable contract for an **AXM HEAD Compute Fabric Edge Demonstrator**. It joins three previously separate objects without making any of them a hidden runtime dependency:

```text
MARY-style bounded work and route semantics
+
admitted Estate fabric and recovery semantics
+
removable cartridge and save custody
```

The laptop and attached RTX 3090 are reference embodiments. They are not mission identity, constitutional state, or a required production topology. The durable object is the mission volume: immutable cartridge law, mutable save custody, observed route evidence, a non-authoritative cache, cold-successor reconstruction, and a standalone verifier.

## Exact supplier coordinates

```text
admitted audit runtime
BigBirdReturns/ai-execution-audit
commit 772ce582e1b19b7a2060c50be8ebf40c1f8723b2
tree   3f708c52782784e687cf1f0b68fd7d37a507ef4c

admitted physical-flight execution floor
BigBirdReturns/ai-execution-audit
commit d31e59f5fd30e57b1917c00832b189ee2ea3e12f
tree   2a6a155e9615eb847781f87566bac32d4c9dc126
physical flight executed: false

qualified-draft MARY Metabolism supplier
BigBirdReturns/mary-portable
commit 9151e0b8de973faede371c816db2602c47b854bd
tree   4a43991b0178919ebfaedae120d7cd96b20091de
admitted to mary-portable main: false
```

The supplier coordinates are evidence and design inputs. The profile also freezes the exact MARY work-unit, route-descriptor, and estate-phase schemas together with the admitted Estate seat-snapshot, route-selection, and worker-lease schemas. This implementation imports no MARY package, Estate checkout, sibling repository, network service, model provider, or external Python dependency.

## Intake transaction

The intake mechanism receives a bounded task, a current equipment observation, and a complete set of independently described routes. It evaluates every route separately against the task's capabilities, privacy lane, validator, memory, wall-time budget, and present availability. It retains every route and every exclusion reason before choosing one route.

The transaction has exactly three terminals:

```text
QUALIFIED_ASSEMBLY
  The interface is declared and read-only, the observation is fresh,
  the adapter is present, and at least one complete route is eligible.

QUALIFICATION_PLAN
  The equipment is intelligible, but a named adapter, verifier,
  capability, memory floor, privacy lane, or budget property is missing.

HOLD
  The interface is undeclared, the probe is not read-only, the
  observation is stale, or the requested authority class is withheld.
```

No terminal represents execution. The demonstrator does not invoke equipment, mutate a device, run a model, or promote a task into an occurrence. It proves only the intake, route-evaluation, portable-custody, and verification membrane.

## Route and fabric law

A route is an independently sufficient execution boundary. The evaluator never sums memory across routes. Two 8 GB routes do not satisfy a 12 GB requirement. An RTX 3090 route may be preferred because it is faster or richer, while the resident CPU route remains separately eligible and available as the personal floor.

The fixed qualified fixture proves:

```text
optional RTX 3090 route selected
resident CPU floor independently eligible
RTX 3090 route removed
same mission and save remain unchanged
resident CPU route becomes selected
```

The route is therefore a replaceable organ. It is not the mission.

## Removable mission volume

The builder emits this closed structure:

```text
MANIFEST.json

CARTRIDGE/
  mission.json
  work-unit.json

SAVE/
  state.json
  ledger.jsonl

ROUTES/
  equipment-observation.json
  candidate-routes.json
  intake-decision.json

CACHE/
  host-specific, replaceable, non-authoritative bytes

RECOVERY/
  cold-successor.json
  verify_volume.py

PUBLIC/
  status.json
```

`CARTRIDGE/mission.json` carries immutable mission identity, invariant references, and the named-human authority boundary. `CARTRIDGE/work-unit.json` carries the complete bounded task and binds it to the exact qualified-draft MARY work-unit schema and supplier digest. `SAVE/state.json` binds the current frontier and unresolved obligations to the exact cartridge and work unit. `SAVE/ledger.jsonl` preserves the intake decision as an append-only event. `ROUTES/equipment-observation.json` binds the equipment observation to the MARY estate-phase schema. `ROUTES/candidate-routes.json` preserves every candidate route, its MARY route identity, its Estate seat coordinate, and the complete route denominator. `ROUTES/intake-decision.json` binds those objects and records the terminal. `RECOVERY/` answers the cold-successor questions and carries a standard-library verifier. `PUBLIC/status.json` exposes only synthetic terminal state and explicit non-claims.

The standalone verifier does not trust the stored decision. It validates the complete work unit, equipment observation, and route denominator, reevaluates every route independently, reconstructs the expected terminal and selected route, and requires byte-for-byte equality with the stored decision. A forger who changes the candidate denominator and correctly recomputes every affected digest still fails when the stored decision no longer follows from the supplied task and routes.

`CACHE/` is excluded from the volume identity and may be deleted, replaced, or regenerated. Unmanifested files anywhere else fail verification. A cache mutation cannot change the cartridge, save, decision, or volume identity.

## Commands

From the repository root:

```powershell
$Tool = 'mating_surface\anchor_node\axm-head-edge-demo.ps1'
$Profile = 'mating_surface\anchor_node\axm-head-edge-demo-profile-01.json'
$Fixtures = 'mating_surface\anchor_node\fixtures\axm-head-edge-demo-cases-01.json'

& $Tool validate-profile $Profile
& $Tool validate-fixtures $Profile $Fixtures

& $Tool decide `
  $Profile `
  $Fixtures `
  qualified-gpu-with-resident-fallback

& $Tool build-volume `
  $Profile `
  $Fixtures `
  qualified-gpu-with-resident-fallback `
  --out $env:TEMP\axm-head-qualified-volume

python $env:TEMP\axm-head-qualified-volume\RECOVERY\verify_volume.py `
  $env:TEMP\axm-head-qualified-volume
```

The Python entrypoint is equivalent:

```text
python mating_surface/anchor_node/axm_head_edge_demo.py ...
```

A build target must not already exist. The standalone verifier can be copied with the volume and run from a foreign working directory. It imports no repository module.

## Fixed fixture campaign

The committed catalog exercises four cases:

```text
qualified-gpu-with-resident-fallback
qualification-plan-missing-adapter
hold-undeclared-mutation-interface
qualification-plan-no-memory-pooling
```

The twenty-three-witness conformance suite additionally covers the exact supplier-schema join, complete work-unit and route-denominator custody, optional-organ removal, stale observations, unknown fields, deterministic volume construction, LF/CRLF source equivalence, cache non-authority, unmanifested-file refusal, cartridge tamper, semantic cartridge/save mismatch after byte-level re-signing, decision self-identity recomputation, independent decision reconstruction after a fully re-signed route-denominator change, public privacy, and foreign-directory standalone verification.

## Relationship to physical flight 01

This increment does not replace issue #37. It gives the future physical campaign a concrete removable-volume object and equipment-intake denominator. The physical flight must still establish the real laptop resident floor, the real attached 3090 route, measured acceleration, post-removal continuity, two actual host classes, cold succession, private evidence sealing, and a body-free public disposition.

The next physical join should replace the invented equipment observation and route evidence with private `private_local_attested` receipts while retaining the exact public schemas and non-claim boundary defined here.

## Claim boundary

This candidate proves a provider-free synthetic intake contract, exact MARY and Estate supplier-schema binding, complete task and route-denominator custody, independently reconstructed per-route evaluation, deterministic terminal classification, immutable cartridge and mutable save binding, non-authoritative cache semantics, portable cold-successor state, and standalone verification.

It does not prove that arbitrary equipment can be understood automatically, that an adapter is safe, that a task was executed, that a model output is correct, that the laptop or RTX 3090 is physically qualified, that the private flight completed, or that representative operator, field network, operational C2, production Lattice, targeting, engagement, effector, or weapons qualification or authority exists.

## Control question

Can a bounded task and an observed equipment candidate produce a qualified assembly, exact qualification plan, or truthful hold while the mission cartridge, save frontier, unresolved obligations, human authority boundary, and cold-successor answer remain independent of the selected route, optional accelerator, host-specific cache, original host, and repository history?
