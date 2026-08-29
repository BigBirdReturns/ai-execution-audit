# AXM HEAD Physical Long-Haul Join 01

## Object classification

`AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2` is a postflight public verification contract. It is not a preflight card, execution conductor, private packet, mission volume, hardware controller, worker scheduler, listener, evidence-body repository, or authorization source. Its only consequential positive terminal is `PRIVATE_SELF_ATTESTED`, which means that a locally supplied `private_local_attested` receipt denominator survived independent reconstruction and produced a body-free self-attested disposition. That terminal does not qualify the physical Estate, a representative operator, a field network, operational C2, production Lattice, or any mission, command, targeting, engagement, effector, or weapons authority.

Issue `BigBirdReturns/ai-execution-audit#49` owns this contract-development transaction. Issue #37 remains the sole private physical-flight execution coordinate. This product cannot initialize or advance issue #37, and issue prose cannot substitute for a private receipt.

## Exact admitted source graph

The profile freezes five public roles and keeps them semantically distinct:

```text
AXM removable-volume supplier
  commit b452bb32e26249deab90db124f157bc62ad0850d
  tree   c557bddc17ad62f6ad36bac5a6ef57338429a951

STC MARY conductor
  commit 772ce582e1b19b7a2060c50be8ebf40c1f8723b2
  tree   3f708c52782784e687cf1f0b68fd7d37a507ef4c

frozen physical-flight execution floor
  commit d31e59f5fd30e57b1917c00832b189ee2ea3e12f
  tree   2a6a155e9615eb847781f87566bac32d4c9dc126

admitted preflight review-card contract
  commit ec61bc3488cb5ae06ed9db2862a9f6910d310a79
  tree   d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67

private execution ledger
  issue #37
```

The admitted preflight contract is useful source law. It supplies the exact review-card phase sequence, packet-stage denominator, receipt-class denominator, stop conditions, and the boundary between review and later authorization. It is mechanically incapable of acting as the named human, a physical observation, a packet-stage receipt, or proof that the campaign occurred. A complete postflight source binding must carry a body-free preflight disposition with terminal `READY_FOR_HUMAN_REVIEW`, exactly twelve card actions, and zero authorized card actions. A separate later `stc-mary/named-human-authorization@1` receipt must identify a named-human actor class and precede every physical observation and packet receipt.

## Closed ten-object denominator

The version-2 object set is exactly:

```text
axm-head/physical-long-haul-profile@2
axm-head/physical-flight-source-binding@2
axm-head/physical-route-attestation@2
axm-head/continuity-attestation@2
axm-head/two-cell-attestation@2
axm-head/successor-attestation@2
axm-head/private-flight-disposition-binding@2
axm-head/physical-long-haul-join@2
axm-head/physical-long-haul-verification@2
axm-head/physical-long-haul-public-status@2
```

Every object uses exact-key validation, canonical UTF-8 JSON, bounded strings and arrays, closed enums, strict JSON Boolean and integer typing, and content-derived identity. Unknown fields refuse rather than becoming future authority or evidence channels.

## Join terminals

The join terminal denominator is closed to:

```text
PREPARED_NOT_ARMED
PRIVATE_SELF_ATTESTED
HOLD
```

`PREPARED_NOT_ARMED` requires exact admitted public sources and a complete body-free preflight review disposition, while the entire private postflight receipt denominator remains absent. The terminal confirms source readiness only. It states that no private flight has been proven.

`PRIVATE_SELF_ATTESTED` requires one complete `private_local_attested` denominator. The verifier independently reconstructs every consequential predicate listed below, requires a distinct named-human authorization receipt, and requires the detached sealed-package verifier to report `PASS`. The public result remains self-attestation only.

`HOLD` preserves a well-shaped input while naming every failed semantic predicate. Synthetic evidence, incomplete receipt sets, preflight-as-authorization, source drift, route mismatch, continuity failure, same-host cells, automatic reunion merge, successor forgery, stage-chain damage, sealed verification failure, claim promotion, and authority promotion all terminate here.

Malformed JSON, unknown fields, content-ID forgery, private-material fields, credential-shaped content, network endpoints, paths, host identities, or invalid primitive types produce a verifier-level `REFUSED` envelope rather than a join terminal.

## Required private reconstruction

The local input contains six body-free private object classes after the source binding: route, continuity, two-cell, successor, private disposition, and the named-human authorization and stage receipts nested within the disposition. The verifier derives the following predicates rather than trusting them as stored conclusions:

```text
public source coordinates exact
preflight source and verifier identities exact
preflight terminal READY_FOR_HUMAN_REVIEW
preflight action denominator 12
preflight authorized action count 0
preflight phase, stage, stop-condition and receipt-class denominators exact
named-human authorization distinct from the preflight receipt
authorization precedes physical observation and packet receipts
complete sixteen-stage denominator retained
fifteen PASS terminals retained
RESTORE_LINK_HOLD_CONFLICT = HUMAN_REQUIRED
stage receipt IDs unique
stage predecessor chain complete
stage timestamps monotonic and authorization-bound
public evidence body count = 0
private evidence body count > 0
resident route independently verified
accelerator route independently verified
memory sufficiency evaluated per route without pooling
accelerator output, semantic identity and classification identity unchanged
accelerator throughput greater than resident throughput
post-removal resident output reproduced
canonical mission state unchanged
Lattice unnecessary for local continuity
two complete cells independently verified
two actual host classes distinct
two branches distinct and both retained
automatic reunion merge false
at least one unresolved reconciliation obligation retained
replacement HEAD class distinct from original HEAD class
original host and repository history absent from successor dependencies
six cold-successor answers independently reconstructed
sealed evidence root cross-bound
detached sealed-package verification = PASS
source public disposition content digest exact
self-attestation claim exact
all stronger qualifications false
authority none
```

The route law forbids pooled independent memory. Both the resident route and the optional accelerator route must individually meet the declared memory floor. The optional accelerator may improve throughput only; it cannot become mission identity, canonical state, or an authority source.

## Six cold-successor answers

The successor cannot supply free-form answers that merely agree with its own manifest. The verifier derives exact answers from the cartridge, canonical state, named-human authorization receipt, sealed evidence root, unresolved-obligation count, and next-safe-action field, then requires equality for:

```text
whatMission
currentState
whoMayAct
whatProvesIt
whatRemainsUnresolved
nextSafeAction
```

Changing any answer and recomputing the successor content identity still produces `HOLD`.

## Private-material exclusion membrane

The local input may carry body-free content references, counts, route classes, host classes, bounded performance units, timestamps, terminal states, and content identities. It may not carry a private path, evidence filename, hostname, seat identity, hardware serial, network endpoint, credential, environment value, operator record, stdout, stderr, telemetry body, evidence body, or sealed package body.

The public status contains only exact public source coordinates, content-derived object IDs, route classes, bounded performance measurements, distinction booleans, counts, terminal state, reason codes, non-claims, and the fixed claim boundary. The verifier scans the complete authenticated output before release.

## External verifier authentication

`verify_axm_head_physical_long_haul_join.py` does not authenticate itself. `axm_head_physical_long_haul_join.py verify` is the external bootstrap. It reads and hashes the frozen verifier bytes, refuses a digest mismatch before execution, writes exactly those measured bytes into a temporary foreign directory, executes the measured copy with bytecode generation disabled, validates the direct receipt, and only then marks the envelope `bootstrapAuthenticated=true`.

Direct invocation of the standalone verifier remains truthful and reports `bootstrapAuthenticated=false`.

## Synthetic qualification boundary

The permanent fixture catalog contains only harmless invented shapes. No fixture uses `private_local_attested`, no fixture expects `PRIVATE_SELF_ATTESTED`, and every fixture public status retains `privatePhysicalFlightCompleted=false`. The complete synthetic private shape proves that the reconstruction logic can close all semantic predicates while still terminating `HOLD` because synthetic evidence cannot attest a physical campaign.

The focused suite separately exercises the private terminal in memory by retiering a complete body-free shape to `private_local_attested`. That witness creates no public fixture, no hosted physical receipt, no mission volume, and no claim that the Estate campaign occurred.

## Commands

Validate the frozen product:

```powershell
$Join = 'mating_surface\anchor_node\axm-head-physical-long-haul-join.ps1'
& $Join validate-profile
& $Join validate-fixtures
```

Emit one harmless synthetic fixture:

```powershell
& $Join emit-fixture prepared-exact-public-sources-no-private-flight `
  --out C:\TEMP\prepared-input.json
```

Authenticate the verifier and evaluate one local body-free input:

```powershell
& $Join verify C:\PRIVATE\BODY-FREE\physical-flight-join-input.json `
  --out C:\PRIVATE\BODY-FREE\physical-flight-join-receipt.json
```

The output location must not already exist. The command performs no hardware action, launches no worker, creates no listener, and writes nothing to issue #37. It verifies an already completed private receipt denominator.

## Private evidence provenance trust root

`PRIVATE_SELF_ATTESTED` is unavailable from self-consistent input bytes alone. The input must carry one detached `axm-head/private-evidence-provenance@2` signature over the exact source binding, five content-addressed private objects, complete stage-receipt identity sequence, and sealed-package disposition digests. The profile freezes the RSA SHA-256 public trust root. The corresponding private signing key remains outside the repository and is used only through `sign-private-provenance`; it authenticates evidence provenance and grants no mission or command authority. Synthetic fixtures carry no provenance signature and cannot select the private terminal.

The library function `bootstrap_verify()` is silent and returns the receipt. Only the CLI `verify` command emits canonical receipt bytes to stdout.

## Claim boundary

This product may qualify the postflight contract, exact source binding, distinct authorization boundary, receipt reconstruction rules, `PRIVATE_SELF_ATTESTED` self-attestation terminal, authenticated verifier, deterministic bytes, and private-material exclusion membrane. It may not claim that the private workstation exists, that issue #37 ran, that any hardware was attached or removed, that two physical cells or a replacement HEAD actually existed, that a sealed private package was produced, or that any stronger qualification or authority has been granted merely because this source code or its synthetic tests exist.

## Control question

Can an independently authenticated local verifier reconstruct the complete private continuity, partition, reunion, successor, and sealed-package predicates from body-free `private_local_attested` receipts, while making the admitted preflight card, synthetic evidence, source coordinates, hardware identity, and self-consistent forgery incapable of manufacturing physical evidence or authority?
