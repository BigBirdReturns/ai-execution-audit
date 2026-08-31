# STC MARY private flight conductor and evidence workstation

The conductor binds the admitted local toolchain, offline carrier, flight-plan compiler, and private packet into one restart-safe private campaign root. It does not perform a physical action, create an evidence body, confirm an operator question, record a packet stage, or promote any qualification claim. Its only canonical inputs are an immutable private configuration, an exact generated path map, the seven identified conductor source files, and the receipts produced by the already admitted instruments.

The execution floor remains the detached checkout admitted at:

```text
commit: c9f4f96ebcc790ffbcc779a1c1f8f32543a8962f
tree:   8e6335cdcc196931d4fbf911ae2d1f6fd2352c29
```

The conductor itself is a later source layer. Run it from its admitted repository checkout or from the exact seven-member source archive produced by qualification, and point `--repository` at a separate detached `c9f4f96...` execution checkout. This separation preserves the frozen physical-flight toolchain while allowing the operator workstation to be admitted afterward.

## Permanent source set

The conductor identifies these exact members at initialization:

```text
.github/workflows/stc-mary-flight-conductor-01.yml
mating_surface/anchor_node/STC-MARY-FLIGHT-CONDUCTOR-RUNBOOK.md
mating_surface/anchor_node/conformance/test_stc_mary_flight_conductor.py
mating_surface/anchor_node/stc-mary-flight-conductor-profile-01.json
mating_surface/anchor_node/stc-mary-flight-conductor.ps1
mating_surface/anchor_node/stc_mary_flight_conductor.py
mating_surface/anchor_node/stc_mary_local/halo3_seat.py
```

Every workstation records the ordered member denominator, member byte counts, member SHA-256 digests, and one source-set content identity. Later source-byte drift refuses the `admitted_checkout` phase.

## Preconditions

Prepare two local coordinates:

1. An exact detached, clean checkout of `c9f4f96ebcc790ffbcc779a1c1f8f32543a8962f` for the admitted execution tools.
2. A private evidence parent outside both repositories. It must already exist and may not be a filesystem root, the user home, the current directory, or any path overlapping the execution checkout.

Declare exactly four private artifact coordinates:

```text
cartridge
model
verifier
storage
```

The labels may not duplicate, the coordinates must exist, symlink roots are refused, and no artifact may overlap another artifact, the execution repository, or the generated workstation.

Set `STC_MARY_PYTHON` when the desired Python 3.11-or-later interpreter is not the default `python` command.

## Validate the frozen profile

From the admitted conductor source tree:

```powershell
$Conductor = 'PATH_TO_CONDUCTOR_SOURCE\mating_surface\anchor_node\stc-mary-flight-conductor.ps1'
& $Conductor validate-profile
```

The profile binds the execution commit and tree, twelve-phase denominator, required artifact labels, exact HALO3 Seat identity, permitted Thunderbolt transport class, initial CUDA-index observation range, deterministic feed coordinates, no-network boundary, zero external services, zero operational credentials, and `authority: none`.

## Initialize one immutable workstation

Use a new direct child of the private parent. The dedicated name pattern is `stc-mary-flight-conductor-*`.

```powershell
$Repo = 'PATH_TO_DETACHED_D31E59F_CHECKOUT'
$PrivateParent = 'PATH_TO_EXISTING_PRIVATE_PARENT'
$Workstation = Join-Path $PrivateParent 'stc-mary-flight-conductor-flight-01'

& $Conductor init `
  --repository $Repo `
  --private-parent $PrivateParent `
  --out $Workstation `
  --campaign-label 'PRIVATE-STC-MARY-FLIGHT-01' `
  --cuda-device-index INITIAL_OBSERVED_INDEX `
  --halo3-product-name 'NVIDIA GeForce RTX 3090' `
  --halo3-gpu-uuid 'GPU-EXACT_UUID' `
  --halo3-pci-bus-id '00000000:BB:DD.F' `
  --halo3-pnp-instance-id 'PCI\VEN_10DE&DEV_2204&EXACT_INSTANCE' `
  --halo3-transport-class 'thunderbolt_egpu' `
  --halo3-transport-anchor-pnp-instance-id 'PCI\VEN_8086&DEV_15DA&EXACT_THUNDERBOLT_ANCHOR' `
  --artifact 'cartridge=PATH_TO_STC_CARTRIDGE' `
  --artifact 'model=PATH_TO_MODEL_OR_EXECUTABLE' `
  --artifact 'verifier=PATH_TO_INDEPENDENT_VERIFIER' `
  --artifact 'storage=PATH_TO_STORAGE_SUBSTRATE'
```

Initialization refuses a moving branch, dirty checkout, wrong full commit, wrong tree, existing campaign root, repository-local output, unsafe private parent, unknown artifact label, missing label, duplicate label, symlink coordinate, path overlap, placeholder campaign label, invalid GPU UUID/PCI/PnP identity, disallowed transport class, missing Thunderbolt anchor, and out-of-range initial CUDA-index observation. CUDA index is never the Seat identity.

A successful initialization creates only the workstation control surface and the empty `products` parent. It does not create any low-level output root. The control surface contains:

```text
CONDUCTOR-ROOT.json
campaign-config.private.json
path-map.private.json
conductor-source-set.json
operator-flight.ps1
progress-ledger.json
workstation-public-projection.json
products/
```

`campaign-config.private.json`, `path-map.private.json`, and `operator-flight.ps1` are immutable campaign coordinates. Editing any of them refuses workstation verification. A changed coordinate set requires a new campaign root.

## Generated product coordinates

The path map fixes every admitted product under the single workstation root:

```text
readiness-private.json
feed-manifest.json
personal-floor baseline and verification
HALO3 result and verification
post-removal continuity result and verification
comparison receipt
two-cell-verification.json
successor-verification.private.json
local-flight-plan.json
flight-config.generated.json
private packet state
sealed detached verification
public-disposition.json
```

The full absolute map remains private. The public projection carries no path.

## Derive status from receipts

Run status after every low-level transaction or host return:

```powershell
& $Conductor status --workstation $Workstation
```

Status reconstructs the campaign from the immutable control files and current receipts. It does not trust a filename or directory merely because it exists. A present receipt must pass the admitted validator or the conductor's exact schema, content-identity, campaign-binding, evidence-tier, and claim-boundary checks.

The twelve phases are:

```text
admitted_checkout
artifact_coordinates
readiness
feed
personal_floor
halo3
post_halo3_continuity
two_cell_partition
successor_head
flight_plan
private_packet
sealed_flight
```

Each status result carries the current phase, closed, held, and refused counts, exact supporting identities, one next safe action, one wake condition when held, one operator control question, the complete claim boundary, and `authority: none`.

Synthetic two-cell or successor receipts remain `HOLD`. Only `private_local_attested` receipts can close those phases. A valid flight plan remains `HOLD` until all eight gates are `READY`. A private packet remains `HOLD` until its admitted state reports all sixteen stages recorded and `nextStage: null`.

## Render the next operator surface

```powershell
& $Conductor render --workstation $Workstation
```

Render writes `NEXT-SAFE-ACTION.md` from the current ledger. It names one bounded transaction and never claims that the transaction occurred. When `flight_plan` closes, render also creates:

```text
packet-handoff.private.json
packet-handoff.ps1
```

The handoff binds the exact plan identity, generated configuration digest, private packet root, packet runner, campaign label, named-human review requirement, and prohibition on automatic stage recording. It does not initialize, configure, or record the packet.

## Use the exact operator script

`operator-flight.ps1` contains the source-pinned commands and generated private paths for:

```text
readiness census and artifact hashing
feed generation
resident-floor baseline and verification
selected-device HALO3 audition and verification
post-interruption continuity and comparison
two-cell construction and reunion
cold-successor construction
flight-plan compilation
packet handoff coordinates
seal and detached verification coordinates
```

The script leaves all physical actions as explicit human controls. In particular, it does not interrupt HALO3, move a cell bundle, attest a remote host, replace HEAD, answer a packet control question, place an evidence body, or record a stage.

## Verify workstation integrity

```powershell
& $Conductor verify --workstation $Workstation
```

Verification reloads and content-validates the immutable root, recomputes the exact source-set identity, rechecks the detached execution checkout, reconstructs every phase from admitted receipts, compares the persisted ledger and public projection to the reconstructed values, and verifies that any packet handoff was impossible before all eight plan gates closed.

`verify` returns `PASS` when the workstation is internally valid and has no refused phase. Held phases are permitted because the physical campaign may still be incomplete. A refused phase must be repaired by reproducing the relevant admitted receipt or by initializing a new campaign root. Do not edit a receipt into compliance.

## Generate the body-free public projection

```powershell
& $Conductor public-projection --workstation $Workstation
```

An explicit destination may be supplied with `--out`. The projection is constructed from an allowlisted field set and then scanned for private paths, path-shaped strings, endpoints, host fields, credentials, environment values, command output, filenames, and evidence bodies. It carries only campaign and source content identities, phase states, receipt identities, counts, and claim boundaries.

The projection always preserves:

```text
physical Estate qualified: false
representative operator qualified: false
field network qualified: false
operational C2 qualified: false
production Lattice qualified: false
mission authority: none
command authority: none
targeting / engagement / effector / weapons capability: false
network required: false
external services: 0
operational credentials: 0
private evidence bodies committed to public Git: 0
authority: none
```

Even after `sealed_flight` closes, the projection proves only that one private self-attested campaign completed and that its sealed package passed the admitted detached verifier. Any stronger qualification requires a separate evidence-tier review and admission transaction.

## Restart and detached reconstruction

No daemon or database holds progress. After process termination or host restart, rerun:

```powershell
& $Conductor status --workstation $Workstation
& $Conductor verify --workstation $Workstation
```

The same root, source bytes, exact execution checkout, and admitted receipts reconstruct the same campaign identity and phase result. No WAN, cloud account, remote model provider, repository history beyond the frozen execution checkout, or operational credential is required.

## Single-action operator surface

`operator-flight.ps1` is a single-action dispatcher. It accepts exactly one action and rejects a missing, unknown, or additional argument before invoking an execution-floor tool:

```text
readiness
feed
personal-floor
halo3
post-halo3-continuity
two-cell
successor-head
compile-plan
seal
```

Every action first reconstructs the workstation ledger and requires the exact current conductor phase. The script then invokes only the selected bounded transaction, checks each tool exit code, and terminates. It cannot continue into a later phase merely because later commands exist in the generated file.

Before `readiness`, `STC_MARY_PYTHON` must resolve to one exact Python 3.11-or-later file whose Torch probe reports `torch.cuda.is_available() == true` and at least one CUDA device. The operator starts that interpreter through `System.Diagnostics.Process` with shell execution disabled, both native streams redirected independently, and no window. It reads both byte streams concurrently in bounded chunks, retains at most 64 KiB from each stream, terminates the process as soon as either cap is crossed, and refuses a probe that does not complete within sixty seconds. A start failure, nonzero exit, empty stdout, oversized stream, timeout, malformed or multiple JSON stdout, unsupported Python, unavailable CUDA, or zero CUDA devices refuses before `doctor`. Doctor then resolves the configured Seat by exact GPU UUID, PCI bus, PnP instance, product, and Thunderbolt ancestry; the observed CUDA index may change without changing the Seat.

Only stdout is parsed as the single Torch-probe JSON object. Bounded stderr is accepted as local diagnostic output and is never merged into the JSON input, included in an exception body, copied to a public projection, or treated as authority. The stream bodies remain local and are discarded after the decision. After the precheck accepts, `readiness` invokes only `doctor` and stops before feed generation.

`two-cell` advances at most one locally executable subtransaction per invocation:

```text
template-inputs
or
build-cell-pair after complete private inputs exist
or
reconcile-cells after both private host verifications exist
```

It never moves a bundle, performs a host attestation, or selects a conflict winner. `successor-head` builds the successor bundle only and never attests the replacement host. Packet stages remain governed by `packet-handoff.ps1` and the packet runtime. `seal` is available only when the conductor reconstructs `sealed_flight`, which requires the private packet phase to be closed.

A failed or overbroad predecessor workstation remains immutable evidence. After a conductor repair, initialize a new successor workstation rather than editing or continuing an older campaign root.
