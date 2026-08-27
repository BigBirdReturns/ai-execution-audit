# STC MARY private-flight runbook

This runbook operates the admitted STC Mission Cartridge and MARY Portable Command-Intelligence Cell private-flight packet. The packet records one local self-attestation against the closed sixteen-stage harness. It does not independently qualify the physical Estate, a representative operator, field networking, operational C2, production Lattice, mission authority, command authority, targeting, engagement, effectors, or weapons.

## Preconditions

Use an admitted `main` checkout of `BigBirdReturns/ai-execution-audit` and Node.js 24 or later. Keep the working packet, evidence bodies, sealed private run, and local paths outside the public repository. The runtime requires no network service and no operational credential.

From PowerShell, set two dedicated destinations under a private local evidence root. Their parent directories must already exist, and neither destination may already exist.

```powershell
$Repo = 'PATH_TO_ADMITTED_REPOSITORY'
$Packet = 'PATH_OUTSIDE_REPOSITORY\stc-mary-private-flight-local-01'
$Sealed = 'PATH_OUTSIDE_REPOSITORY\stc-mary-private-flight-sealed-local-01'
$Runner = Join-Path $Repo 'mating_surface\anchor_node\stc-mary-private-flight.ps1'
```

## Initialize

```powershell
& $Runner init $Packet 'PRIVATE-STC-MARY-FLIGHT-01'
& $Runner status $Packet
```

Initialization creates one marked packet root, `flight-config.json`, `packet-state.json`, and sixteen ordered stage directories. Each stage directory contains `INSTRUCTIONS.md`, `stage-attestation.json`, and an empty `evidence` directory.

## Configure the flight

Edit `flight-config.json` and provide:

- the exact campaign label created during initialization;
- the SHA-256 digests of the admitted cartridge and source objects used for this flight;
- private identity classes for the personal floor, HALO3, initial HEAD, successor HEAD, GRACE, Lattice membrane, and both partition cells;
- one canonical mission-state SHA-256 digest that must remain unchanged throughout the campaign.

Apply the configuration with a separate copy of the completed file:

```powershell
& $Runner configure $Packet 'PATH_TO_COMPLETED_CONFIG.json'
& $Runner status $Packet
```

Configuration binds every stage draft to the same canonical state digest and inserts the declared private identity classes. Recorded stages lock the configuration, so complete this step before beginning the campaign.

## Execute and record each stage

Process the stage directories in numeric order. For each stage:

1. Perform the operator action in `INSTRUCTIONS.md`.
2. Place every local evidence body in that stage's `evidence` directory.
3. Edit `stage-attestation.json` with the measured observation.
4. Keep the prescribed terminal state unchanged.
5. Set `operatorConfirmed` to `true` only after the control question is satisfied.
6. Record the stage.

```powershell
& $Runner record $Packet VERIFY_INPUTS
& $Runner status $Packet
```

Repeat for the remaining stages in this exact order:

```text
MOUNT_PERSONAL_FLOOR
BIND_GRACE
RUN_PERSONAL_FLOOR_BASELINE
ATTACH_HALO3
RUN_HALO3_ACCELERATED
REMOVE_HALO3
VERIFY_PERSONAL_FLOOR_CONTINUITY
REMOVE_LATTICE
VERIFY_LOCAL_CONTINUITY
PARTITION_TWO_CELLS
RESTORE_LINK_HOLD_CONFLICT
REPLACE_HEAD
REBUILD_PROJECTIONS
COLD_SUCCESSOR_VERIFY
SEAL_PRIVATE_EVIDENCE
```

Recording is sequential and fail-closed. A stage cannot record without explicit operator confirmation and at least one regular evidence file. Each evidence file is content-addressed at record time. Any later byte drift blocks sealing. The reconnection stage must remain `HUMAN_REQUIRED`, retain both divergent cell states, and preserve one unresolved reconciliation obligation.

## Seal the private flight

After all sixteen stages are recorded and `status` reports `nextStage: null`, seal the packet into a new dedicated directory outside the repository:

```powershell
& $Runner seal $Packet $Sealed
& $Runner verify-sealed $Sealed (Join-Path $Sealed 'detached-verification.json')
```

The packet retains all private evidence bodies. The sealed directory contains the digest-only private run, body-free public disposition, detached verification, static review surface, and exact manifest. The sealer rehashes every evidence body and refuses any change since stage recording.

## Public return boundary

Only `public-disposition.json` is suitable for a separately reviewed public-repository transaction. It contains content identities, counts, and claim boundaries. It contains no evidence body, local path, host identity, endpoint, credential, or telemetry body. The sealed private run and all underlying evidence remain local.

A successful local seal records that one private self-attested flight completed. Every independent qualification field remains false until a separate evidence-tier review explicitly admits a stronger claim.
