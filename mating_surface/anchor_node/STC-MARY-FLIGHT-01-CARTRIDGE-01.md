# STC Mission Cartridge 01

This product is the immutable public mission-law cartridge for the first private STC MARY physical flight governed by issue #37 and constructed under issue #57. It gives the conductor one exact `cartridge` artifact without selecting the private model, verifier, storage substrate, host, evidence path, or operator record. It is a source object and portable bundle. It is not a physical receipt, authorization, mutable save, execution result, or qualification claim.

MARY Portable and the cartridge are separate actors. MARY Portable v0.2.0 is the admitted tenant instrument that performs bounded machine interlocution and emits independently verifiable campaign packets under named-human authority. STC Mission Cartridge 01 states the mission identity, work-unit law, semantic source graph, stage and gate denominators, invariants, and authority boundary that a compatible conductor may bind. MARY may carry the cartridge. MARY does not become the cartridge, and the cartridge does not inherit MARY's runtime role.

## Semantic source graph

The cartridge semantic identity freezes exactly four public source roles:

```text
MARY Portable tenant:
BigBirdReturns/mary-portable
commit f382633d7349a5d748d2f0b6092f96570f6e5d26
tree   a18f6612b8119beac68292ef4d7f8a5b35e1b0fa
release v0.2.0
archive sha256 bd67c865032ae0977d8c2ada1c07b5e7564fe2ddf6e65f19b63ad41749359009

AXM removable mission-volume supplier:
commit b452bb32e26249deab90db124f157bc62ad0850d
tree   c557bddc17ad62f6ad36bac5a6ef57338429a951

physical-flight preflight review card:
commit ec61bc3488cb5ae06ed9db2862a9f6910d310a79
tree   d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67

physical-flight execution floor:
commit d31e59f5fd30e57b1917c00832b189ee2ea3e12f
tree   2a6a155e9615eb847781f87566bac32d4c9dc126
```

The executable conductor is deliberately excluded from the profile, source binding, cartridge identity, mission identity, work-unit identity, public status, manifest, and bundle identity. Compatible conductor repair lineage is non-authoritative operator provenance, retained outside the portable cartridge:

```text
772ce582e1b19b7a2060c50be8ebf40c1f8723b2
original admitted conductor

ccc6f1bb817614d0948900499c80f4f91e8bade0
readiness artifact-identity compatibility

1047b90d2c2077cff297b9d5e24e333fe7dcf8cc
single-action authorization containment

a99c1c76daf383edd31ada2e3a8f8bf5c57a7888
native stdout/stderr separation

dd486472a8c610a20ee062dd6746c86fe8ede4b4
bounded incremental streams and finite timeout
```

Updating this compatible operator provenance cannot alter cartridge semantics, authorize execution, or promote a physical or authority claim. Issue #37 remains the sole private execution coordinate. Issue #49 remains the postflight join coordinate.

## Cartridge law

The mission law binds:

```text
mission name:
STC Mission Cartridge 01

campaign label:
PRIVATE-STC-MARY-FLIGHT-01

named-human bind:
GRACE

system authority:
none

conductor phases:
12

flight-plan gates:
8

private packet stages:
16
```

The work-unit law binds the deterministic integer linear aperture campaign already admitted by the local toolchain:

```text
records: 262144
features: 32
classes: 8
seed: 20260827
resident floor: python
optional accelerator: torch-cuda
privacy lane: private-local
authority class: compute-only
```

The resident Python route is the mission-closed floor and independent semantic reference. The optional accelerator may improve throughput only. It may not change semantic or classification identity, become necessary for continuity, own canonical state, or acquire authority. The resident floor must reproduce the accepted result after the declared reversible accelerator interruption.

The cartridge preserves the complete two-cell, `HUMAN_REQUIRED` reunion, replacement-HEAD, cold-successor, private evidence, and authority-none invariants. It does not contain a mutable frontier. Mutable state, receipts, unresolved obligations, and later acceptance remain in the save, conductor workstation, and private packet.

## Closed bundle

The builder emits exactly seven files under three directories:

```text
MANIFEST.json

CARTRIDGE/
  mission.json
  work-unit.json

RECOVERY/
  profile.json
  source-binding.json
  verify_cartridge.py

PUBLIC/
  status.json
```

The manifest content-addresses every member and derives one bundle identity. The mission derives one cartridge identity and one mission identity from the exact profile, source binding, work-unit identity, invariant denominator, phase sequence, gate sequence, and packet-stage sequence. `CACHE/` is intentionally absent because this artifact carries mission law only.

The initial terminal is always:

```text
PREPARED_NOT_ARMED
```

The public status always reports that the private coordinate is unbound, the private preflight is uncompiled, human review is incomplete, authorization is absent, the workstation is uninitialized, physical execution has not started, packet progress is `0 / 16`, evidence-body counts are zero, and authority is `none`.

## Build and verification

From the admitted source checkout:

```powershell
$Repo = 'PATH_TO_EXACT_SOURCE_CHECKOUT'
$Tool = Join-Path $Repo 'mating_surface\anchor_node\stc-mary-flight-01-cartridge.ps1'
$Profile = Join-Path $Repo 'mating_surface\anchor_node\stc-mary-flight-01-cartridge-profile-01.json'
$PrivateParent = 'PATH_TO_EXISTING_PRIVATE_PARENT_OUTSIDE_EVERY_REPOSITORY'
$Cartridge = Join-Path $PrivateParent 'stc-mary-flight-01-cartridge-01'
$Verdict = Join-Path $PrivateParent 'stc-mary-flight-01-cartridge-01-verdict.json'

& $Tool validate-profile $Profile
& $Tool build $Profile --out $Cartridge
& $Tool verify $Cartridge --out $Verdict
& $Tool public-projection $Cartridge
```

The build destination must be a new directory beneath an existing parent outside every Git repository. The builder refuses an existing destination, repository-local output, filesystem roots, the home directory, the current directory, symlink members, and source drift.

`verify` uses the external bootstrap. The bootstrap first requires the verifier's regular-file size to equal the frozen source length, then performs one bounded read of at most that length plus one byte before hashing. The frozen length is an allocation precondition, so oversized regular or sparse files terminate a structured non-execution refusal before the bootstrap allocates from cartridge-controlled size. The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The isolated launcher injects those same measured bytes into the trusted verifier namespace; the verifier requires the stored `RECOVERY/verify_cartridge.py` member to remain byte-identical to the measured execution bytes, and the bootstrap requires the returned measured digest before it can set `bootstrapAuthenticated = true`. A verifier-member replacement and resigned manifest between measurement and child verification therefore terminates refusal rather than authenticating a different bundle member. Consequently, bootstrap authentication is conditioned on equality between the code bytes executed by the isolated child and the verifier-member bytes incorporated into manifest reconstruction. The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity. Stored semantics are compared through canonical JSON bytes so JSON Boolean and integer substitutions cannot pass through Python equality. The authenticated verdict carries the reconstructed public status in memory, and `public-projection` emits that object without reopening `PUBLIC/status.json`; a concurrent post-verification member replacement therefore cannot enter the projection. The projection route has one authenticated object and performs no second filesystem read of the projected member.

A copied bundle remains verifiable from a foreign working directory with standard-library Python. Repository history, MARY source, the builder, the original checkout, a network service, provider credential, and private evidence are not required. Before resolution, every verification and projection route walks the lexical absolute cartridge coordinate component by component and refuses a symlink or Windows junction in the final component or any ancestor, so the supplied coordinate cannot be retargeted through a linked parent. Before launching the external bootstrap, the tool converts both the cartridge coordinate and any verifier-output coordinate to lexical absolute paths against the caller's current directory. The child working directory may then change without reinterpreting relative arguments or relocating the verdict.

## Private flight handoff

After source admission, copy or build the exact cartridge under private custody and use that directory as the conductor's `cartridge` coordinate:

```powershell
& $Conductor init `
  --repository $ExecutionRepo `
  --private-parent $PrivateParent `
  --out $Workstation `
  --campaign-label 'PRIVATE-STC-MARY-FLIGHT-01' `
  --cuda-device-index 0 `
  --artifact "cartridge=$Cartridge" `
  --artifact "model=$Model" `
  --artifact "verifier=$IndependentVerifier" `
  --artifact "storage=$StorageSubstrate"
```

Before initialization, the admitted preflight card must validate body-free headers for all four coordinates and terminate `READY_FOR_HUMAN_REVIEW` with zero authorized actions, zero workers, zero listeners, no execution, and authority `none`. A named human may then authorize only `INITIALIZE_CONDUCTOR_WORKSTATION`. The cartridge does not supply that authorization.

## Claim boundary

This product may prove that one exact, immutable, independently verifiable Flight 01 mission-law and work-unit cartridge exists. It cannot prove that a private copy was selected, the other three artifacts were bound, a preflight card passed, a human authorized initialization, the workstation exists, readiness ran, HALO3 accelerated anything, two physical cells existed, a replacement HEAD recovered state, a packet stage was recorded, a private evidence body exists, or the flight completed.

```text
physical Estate qualified: false
representative operator qualified: false
field network qualified: false
operational C2 qualified: false
production Lattice qualified: false
mission authority: none
command authority: none
targeting / engagement / effector / weapons capability: false
authority: none
```

The controlling question is whether the artifact remains independently intelligible and verifiable after separation from the repository while staying distinct from MARY, the mutable save, the model, the verifier, the storage substrate, and every private physical receipt.
