# AXM HEAD Edge Demo Contract 01

## Object

This increment defines the first executable **AXM HEAD Compute Fabric Edge Demonstrator** contract. It joins one MARY-style bounded work unit, one observed foreign-equipment candidate, one independently evaluated Estate route denominator, and one removable cartridge and save volume without making MARY, the Estate, a sibling checkout, a provider, or a network service a runtime dependency.

The laptop and attached RTX 3090 are reference embodiments. They are neither mission identity nor constitutional topology. The durable object is the removable volume: immutable cartridge law, mutable save custody, complete route evidence, a non-authoritative cache, cold-successor reconstruction, and a standalone verifier whose identity must be authenticated before execution.

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

The builder and standalone verifier both require these exact coordinates. A structurally valid same-ID profile with any altered repository, commit, tree, or status is refused before volume construction.

## Frozen source trust graph

Version 0.1 closes four independent identities:

```text
profile canonical SHA-256
c6529dbe52c678f8ae7ede650b706b1de22f10f6444dd99a5720e41b03cf7078

fixture catalog canonical SHA-256
82e4bf7e8d18fae61a1e17d1cf758d46004d08dd4b877f933be5c96663b67291

embedded standalone verifier SHA-256
8ca6d225fc162e78fb1af41c9cd89c188491a08fe71a69b58c6c12cd9acf4e44

external bootstrap SHA-256
885a2de66ac339d410bfebed97967fd863e3b7ad77ff3f0e9823ce6c94497d76
```

The profile freezes the exact four-case catalog denominator. The volume carries canonical copies of the governing profile and complete fixture catalog. The standalone verifier independently reconstructs both canonical identities and refuses a rewritten profile, an expanded catalog, a reordered case denominator, or an altered selected fixture even when every affected file digest and `volumeId` has been recomputed.

The embedded verifier is not permitted to authenticate itself. Direct execution truthfully records `bootstrapAuthenticated: false`. An operator must invoke the external `verify_axm_head_bootstrap.py` from the exact reviewed source coordinate or another independently authenticated copy. The bootstrap hashes `RECOVERY/verify_volume.py` before execution and refuses substitution without running the untrusted bytes. A successful bootstrapped verdict records `bootstrapAuthenticated: true` and the exact admitted verifier digest.

## Intake transaction

The intake mechanism receives a bounded task, a current equipment observation, and the complete set of independently described routes. It evaluates every route separately against required capabilities, privacy lane, validator, memory, wall-time budget, availability, interface declaration, observation freshness, and permitted authority class. It retains every route and every exclusion reason before choosing one route.

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

No terminal represents execution. The demonstrator does not invoke equipment, mutate a device, run a model, or promote a task into an occurrence.

## Route and fabric law

A route is an independently sufficient execution boundary. Memory is never summed across independent routes. Two 8 GB routes do not satisfy a 12 GB requirement. An RTX 3090 route may be preferred while the resident CPU remains independently eligible as the personal floor.

The qualified fixture proves:

```text
optional RTX 3090 route selected
resident CPU floor independently eligible
optional route removed
same mission identity retained
same save identity retained
resident CPU route selected
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
  profile.json
  fixture-catalog.json
  verify_volume.py

PUBLIC/
  status.json
```

The authoritative denominator contains twelve files. `CACHE/` is excluded from the volume identity and may be deleted, replaced, or regenerated. An unmanifested file anywhere else fails verification.

The manifest freezes the supplier coordinates, source-schema bindings, profile identity, fixture-catalog identity, verifier identity, four-case denominator, cache policy, cartridge binding, work-unit binding, save binding, equipment binding, complete route denominator, every authoritative file digest, and the exact public non-claim text. `bootstrapRequired` must remain true.

## Independent semantic reconstruction

The verifier does not trust consequential claims merely because they are content-addressed. It loads the admitted profile and full catalog from the volume, selects the exact declared case, and reconstructs:

```text
cartridge
work-unit binding
save state
observed equipment object
complete route denominator
intake decision
ledger event
cold-successor record
public projection
```

The cold-successor answers are derived rather than accepted:

```text
whatMission
currentState
whoMayAct
whatProvesIt
whatRemainsUnresolved
nextSafeAction
```

A caller may change an answer, rewrite every affected file digest, and recompute the volume identity. Verification still refuses because the answer no longer follows from the admitted cartridge, save, equipment, route, decision, obligation, and human-authority state.

The declared `cartridgeSha256` is the SHA-256 of the canonical immutable law body: schema, profile, mission and cartridge identities, invariant references, named-human authority, system non-authority, and cartridge claim boundary. Mutable save state is excluded. The builder and detached verifier independently recompute this digest. A changed invariant or acting-human rule with a stale declared digest refuses even after the volume file rows and `volumeId` are re-signed. If a forger also derives a new digest and rewrites the manifest binding, reconstruction against the admitted catalog law still refuses.

The exact public claim boundary and the distinct cartridge claim boundary are frozen constants. A same-ID profile or fully re-signed volume cannot publish a stronger narrative claim while retaining a passing verdict.

## Commands

From the repository root:

```powershell
$Tool = 'mating_surface\anchor_node\axm-head-edge-demo.ps1'
$Profile = 'mating_surface\anchor_node\axm-head-edge-demo-profile-01.json'
$Fixtures = 'mating_surface\anchor_node\fixtures\axm-head-edge-demo-cases-01.json'
$Volume = Join-Path $env:TEMP 'axm-head-qualified-volume'

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
  --out $Volume

& $Tool verify-volume $Volume
```

The Python entrypoints are equivalent:

```text
python mating_surface/anchor_node/axm_head_edge_demo.py ...
python mating_surface/anchor_node/verify_axm_head_bootstrap.py VOLUME
```

A build target must not already exist. Both verifier entrypoints refuse `--out` when the destination is inside the volume, resolves through a symlink into the volume, or aliases an authoritative volume file. The refusal is emitted only to stdout, so verification cannot mutate the object it just measured. The bootstrap and embedded verifier use only standard-library Python. They may run from a foreign working directory and import no repository module.

## Closed fixture and hostile campaign

The admitted catalog contains exactly these four cases in this order:

```text
qualified-gpu-with-resident-fallback
qualification-plan-missing-adapter
hold-undeclared-mutation-interface
qualification-plan-no-memory-pooling
```

The thirty-eight-witness conformance suite covers the exact source-coordinate join, canonical profile and fixture identities, exact four-case denominator, all three terminal classes, optional-organ removal, stale observations, unknown fields, deterministic volume construction, LF and CRLF source equivalence, external bootstrap verification, truthful direct-verifier non-authentication, complete twelve-file custody, cache non-authority, unmanifested-file refusal, cartridge tamper, semantic save mismatch, decision reconstruction, public privacy, and foreign-directory execution.

The hostile re-signing campaign additionally rewrites and re-signs:

```text
profile provenance
expanded fixture catalog
whatMission
currentState
whoMayAct
whatProvesIt
whatRemainsUnresolved
nextSafeAction
public and manifest claim text
cartridge claim text
cartridge invariant and named-human law
verdict output path overlapping the measured volume
route denominator and decision chain
embedded verifier bytes
```

Every forged transaction must refuse after all affected file sizes, file digests, object identities, and `volumeId` values have been recomputed. The malicious-verifier witness also proves that substituted code is refused before it executes.

## Qualified reference identity

For the admitted qualified fixture under these source bytes:

```text
case
qualified-gpu-with-resident-fallback

terminal
QUALIFIED_ASSEMBLY

decision
axmheaddecision1_110c1f67f8b24f7ae816571fd116ead6533fd33695e79107dfcb011ec4e7fe2b

volume
axmheadvolume1_485650caef636e563d575b987108a86e20dc209b49042ced64c1880b128f9608

manifest SHA-256
8ff47fd36b1af9d3a0d7d6cc693d846648bfd814120e05635aa163d7fa77de09

public projection SHA-256
c0c3f6b8969034bdc87845c692964df9d34680da7168a1aaad258167fe0f286f

authoritative files
12

execution occurred
false

authority
none
```

These identities are synthetic contract receipts. They are not physical-equipment or operator qualification.

## Relationship to physical flight 01

This increment does not replace issue #37. It gives the future physical campaign a concrete removable-volume object, exact equipment-intake denominator, and externally authenticated recovery surface. The physical flight must still establish the real resident floor, real attached accelerator route, measured acceleration, post-removal continuity, two actual host classes, cold succession, private evidence sealing, and a body-free public disposition.

A later physical join must replace invented equipment and route evidence with private `private_local_attested` receipts while retaining the exact public schemas and non-claim boundaries defined here. Citation alone transfers neither authority nor evidence tier.

## Claim boundary

This candidate proves a provider-free synthetic intake contract, exact MARY and Estate supplier-schema binding, closed source and fixture provenance, complete task and route-denominator custody, independently reconstructed route and successor semantics, deterministic terminal classification, immutable cartridge and mutable save binding, non-authoritative cache semantics, portable cold-successor state, and externally bootstrapped standalone verification.

It does not prove that arbitrary equipment can be understood automatically, that an adapter is safe, that a task was executed, that a model output is correct, that the laptop or RTX 3090 is physically qualified, that the private flight completed, or that representative operator, field network, operational C2, production Lattice, targeting, engagement, effector, or weapons qualification or authority exists.

## Control question

Can a foreign successor authenticate the verifier before execution and independently derive the mission, present state, acting human, proof set, unresolved obligations, safe next action, governing public claim boundary, source profile, and complete fixture denominator without accepting any of those consequential answers from mutable bytes inside the volume itself?
