# AXM HEAD Physical Long-Haul Join 01

## Classification

This is the public postflight verification contract governed by issue #49. It is distinct from the admitted preflight review-card contract. The preflight object defines the review-to-authorization boundary. This join consumes the resulting body-free private receipt denominator only after a separate named-human authorization exists and independently reconstructs whether one private campaign may be reported as `PRIVATE_SELF_ATTESTED`.

## Exact public floor

The contract freezes the AXM removable-volume supplier at `b452bb32e26249deab90db124f157bc62ad0850d`, the STC MARY conductor at `772ce582e1b19b7a2060c50be8ebf40c1f8723b2`, the physical execution floor at `d31e59f5fd30e57b1917c00832b189ee2ea3e12f`, and the admitted preflight contract at `ec61bc3488cb5ae06ed9db2862a9f6910d310a79`. Issue #37 remains the sole private execution coordinate.

## Closed object denominator

- `axm-head/physical-long-haul-profile@2`
- `axm-head/physical-flight-source-binding@2`
- `axm-head/physical-route-attestation@2`
- `axm-head/continuity-attestation@2`
- `axm-head/two-cell-attestation@2`
- `axm-head/successor-attestation@2`
- `axm-head/private-flight-disposition-binding@2`
- `axm-head/physical-long-haul-join@2`
- `axm-head/physical-long-haul-verification@2`
- `axm-head/physical-long-haul-public-status@2`

## Terminals

`PREPARED_NOT_ARMED` means the exact public source graph is verified and no private receipt denominator is present. `HOLD` means private-shaped evidence is partial, synthetic, inconsistent, improperly authorized, semantically divergent, insufficiently verified, or violates a non-claim. `PRIVATE_SELF_ATTESTED` requires the complete private-local denominator and remains self-attestation only.

## Reconstruction law

The verifier derives the sixteen-stage chain, fifteen `PASS` terminals, the `HUMAN_REQUIRED` conflict terminal, named-human authorization ordering, resident-route sufficiency, optional-accelerator semantic identity and acceleration, post-removal continuity, Lattice absence, distinct physical host classes, branch retention, replacement-HEAD class distinction, six cold-successor answers, evidence-body counts, sealed verification, private-material scan, and every stronger non-claim. Memory is evaluated per route and is never pooled.

## Custody

The public carrier contains only canonical UTF-8 JSON, source and receipt identities, bounded measurements, class distinctions, counts, terminals, and claim boundaries. It refuses private paths, filenames, hostnames, seat identities, serials, endpoints, credentials, environment values, operator records, stdout, stderr, telemetry, and private evidence bodies. The embedded verifier cannot authenticate itself. The external tool hashes the measured verifier, profile, and fixture bytes before executing the measured verifier from a temporary foreign directory.

## Current authority

Construction and hosted qualification perform no physical action, produce no physical authorization, materialize no mission volume, launch no worker, create no listener, advance no issue #37 receipt, and grant no authority. The synthetic fixture catalog cannot emit `PRIVATE_SELF_ATTESTED`.

## Control question

Can the authenticated verifier reconstruct every consequential physical predicate from a complete body-free private receipt chain while making source admission, preflight review, synthetic evidence, route memory pooling, hardware identity, and self-consistent re-signing incapable of manufacturing physical evidence or authority?


## Private proof-root and single-campaign closure

`PRIVATE_SELF_ATTESTED` now requires a separately custodied `axm-head/private-proof-root@1` that never enters the repository, carrier, public receipt, workflow artifact, stdout, or stderr. The root authenticates one `axm-head/private-proof-envelope@1` over the complete canonical input graph with HMAC-SHA-256. Public bytes alone can reconstruct `PREPARED_NOT_ARMED` and `HOLD`; they cannot manufacture the private terminal.

Every route, continuity, two-cell, successor, authorization, stage, and disposition component carries the same campaign and proof-root coordinates. The verifier rejects mixed campaign or root coordinates and derives these cross-stage links:

```text
BIND_GRACE                          -> authorization receipt
RUN_PERSONAL_FLOOR_BASELINE         -> resident-route receipt
RUN_HALO3_ACCELERATED               -> accelerator-route receipt
VERIFY_PERSONAL_FLOOR_CONTINUITY    -> continuity receipt
PARTITION_TWO_CELLS                 -> two-cell receipt
COLD_SUCCESSOR_VERIFY               -> successor receipt
SEAL_PRIVATE_EVIDENCE               -> sealed-package digest
```

It also requires the accepted output to agree across resident, accelerator, baseline, and post-removal continuity; the canonical mission state to agree across continuity, two-cell parent, successor, packet stages, and disposition; and the successor proof root to identify the separately supplied private root.

The private postflight command sequence is closed:

```powershell
$Join = '.\mating_surface\anchor_node\axm-head-physical-long-haul-join.ps1'

& $Join create-proof-root `
  .\mating_surface\anchor_node\axm-head-physical-long-haul-join-profile-01.json `
  --campaign PRIVATE-STC-MARY-FLIGHT-01 `
  --out PATH_OUTSIDE_REPOSITORY\join-v2-proof-root.private.json

& $Join authenticate-private-input `
  .\mating_surface\anchor_node\axm-head-physical-long-haul-join-profile-01.json `
  .\mating_surface\anchor_node\fixtures\axm-head-physical-long-haul-join-cases-01.json `
  PATH_TO_BODY_FREE_PRIVATE_INPUT `
  --proof-root PATH_OUTSIDE_REPOSITORY\join-v2-proof-root.private.json `
  --out PATH_OUTSIDE_REPOSITORY\join-v2-authenticated-input.json

& $Join build-private `
  .\mating_surface\anchor_node\axm-head-physical-long-haul-join-profile-01.json `
  .\mating_surface\anchor_node\fixtures\axm-head-physical-long-haul-join-cases-01.json `
  PATH_OUTSIDE_REPOSITORY\join-v2-authenticated-input.json `
  --proof-root PATH_OUTSIDE_REPOSITORY\join-v2-proof-root.private.json `
  --out PATH_OUTSIDE_REPOSITORY\axm-head-join-v2-carrier

& $Join verify-join `
  PATH_OUTSIDE_REPOSITORY\axm-head-join-v2-carrier `
  --proof-root PATH_OUTSIDE_REPOSITORY\join-v2-proof-root.private.json `
  --out PATH_OUTSIDE_REPOSITORY\join-v2-verdict.json
```

Creating the authentication root does not authorize or start physical work. The root becomes useful only after issue #37 separately produces a complete body-free private receipt graph. Qualification uses an ephemeral root entirely inside the test process, captures focused-test stdout as empty, and publishes only the `PREPARED_NOT_ARMED` fixture.

```text
profile canonical SHA-256: 86bd2322f7bfc8dce2f211aef806b831b8b69076fdcd52491f6bfd45108a7485
fixture catalog canonical SHA-256: e5ad2cfcf55c8f75c49177f289668be7b6f84b69030ea6fa24ac9566e7dd11f5
standalone verifier SHA-256: 133415014164e66ab5db7d4065ba84b845082dcc035d1aa7a82b4f3c0f301e0e
```


## Authorization receipt identity closure

Named-human authorization and physical execution are separate transactions. The authorization receipt identity must therefore differ from every one of the sixteen physical packet-stage receipt identities. The first stage must point back to the authorization receipt, while the second stage must point to the first stage receipt. Reusing the authorization identity as the first physical receipt is refused even when the complete graph is re-authenticated with the valid private proof root.
