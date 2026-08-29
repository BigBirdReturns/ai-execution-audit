# AXM HEAD Physical Flight Preflight Review Card 01

## Object

This increment defines the public physical-flight preflight review-card contract between the admitted AXM HEAD removable mission-volume supplier and the admitted STC MARY private-flight conductor. It closes the repository-side dependency question before any private physical authorization can exist. The preflight review-card contract validates the exact public floors, accepts only body-free private coordinate headers, and deterministically compiles an operator review card. It does not initialize a workstation, materialize a mission volume, update issue #37, launch a worker, create a listener, observe equipment, execute a task, or authorize an Estate visit.

The carrier begins at `PREPARED_NOT_ARMED`. A later body-free preparation object may reach `READY_FOR_HUMAN_REVIEW` only when the two required checkouts are exact, clean, and detached; all four private artifact coordinates are present as content references without paths or bodies; and the compiled card is byte-equivalent to the admitted phase plan. Every card action remains `authorized: false`. Human review is therefore a separate transaction, and review is not execution authority.

## Exact source graph

```text
owning project
Estate

owning repository
BigBirdReturns/ai-execution-audit

admitted AXM HEAD supplier
commit b452bb32e26249deab90db124f157bc62ad0850d
tree   c557bddc17ad62f6ad36bac5a6ef57338429a951
status admitted

supplier construction record
commit e185b3de109b0fb9be1dddcc33c3d410b8f1fc46
tree   c557bddc17ad62f6ad36bac5a6ef57338429a951
status qualified_then_squash_admitted

admitted STC MARY conductor
commit 772ce582e1b19b7a2060c50be8ebf40c1f8723b2
tree   3f708c52782784e687cf1f0b68fd7d37a507ef4c
status admitted

frozen physical-flight execution floor
commit d31e59f5fd30e57b1917c00832b189ee2ea3e12f
tree   2a6a155e9615eb847781f87566bac32d4c9dc126
status admitted_not_executed

sole physical-flight coordinate
BigBirdReturns/ai-execution-audit#37
```

The source split is deliberate. The conductor remains the admitted operator surface. The older detached floor remains the physical execution source. The AXM supplier supplies the removable-volume and equipment-intake law. This preflight review-card contract binds the three coordinates without moving, replacing, or collapsing them.

## Closed terminals

The preflight review-card contract admits exactly four public preparation terminals:

```text
PREPARED_NOT_ARMED
  The admitted public source graph is bound. No checkouts, private
  coordinate headers, execution card, authorization, workers, listeners,
  or physical activity exist.

HOLD
  A body-free preparation is incomplete or unsafe. Examples include a
  missing checkout, moving or dirty checkout, incomplete four-artifact
  denominator, unsafe coordinate header, or absent compiled card.

READY_FOR_HUMAN_REVIEW
  Both exact checkouts and all four body-free private coordinate headers
  are bound, and the deterministic twelve-phase card is present. Every
  action remains unauthorized. The only next transaction is named-human
  review under issue #37.

REFUSED
  A source coordinate drifts; state identity is forged; a caller supplies
  a mismatched card; physical activity has begun; workers or listeners
  exist; authorization is present; authority is promoted; or private
  coordinate syntax exceeds the closed body-free schema.
```

No terminal authorizes physical execution. `READY_FOR_HUMAN_REVIEW` means that the software side has produced the reviewable denominator. It does not mean that the operator may perform any listed action.

## Body-free preparation state

The preparation state binds the preflight review-card contract contract, exact source coordinates, issue #37, two checkout receipts, four private coordinate headers, zero activity, absent authorization, and authority `none`. The private headers contain only:

```text
label
contentRef
exists
symlinkRoot
overlapFree
```

The four labels are exactly:

```text
cartridge
model
verifier
storage
```

A header may carry a `sha256:` content reference. It may not carry a path, hostname, endpoint, credential, command output, telemetry body, evidence filename, evidence body, or operator record. Duplicate labels, unknown labels, invalid content references, missing objects, symlink roots, and overlapping coordinates hold or refuse before a card can be compiled.

## Deterministic operator review card

When both checkouts and all four private headers close, the compiler emits one twelve-action card derived from the admitted conductor phase sequence:

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

Each action carries its ordinal, phase, action class, command surface, operator action, required receipt classes, human-required flag, physical-action flag, complete stop-condition denominator, and `authorized: false`. The card identifies the first physical action and preserves the complete sixteen-stage private packet denominator through the governing profile.

The compiled card is content-bound to the exact checkout set, private-coordinate set, preparation basis, issue #37, phase plan, stop conditions, and claim boundary. A caller-supplied alteration, including changing one action to authorized, produces `EXECUTION_CARD_MISMATCH` even when the state identity is recomputed.

The public card is a preflight review object. A later private action card must still add the actual host role, device or physical object, irreducible physical operation, exact command, expected receipt, stop condition, and rollback for the one bounded next action. Until that later card is independently verified and explicitly accepted by the named human, there is no Estate visit and nothing for the operator to touch.

## Stop conditions

Every action inherits the complete public stop denominator:

```text
source_coordinate_drift
dirty_or_moving_checkout
private_coordinate_mismatch
unexpected_worker_or_listener
authorization_field_present
authority_not_none
receipt_refusal
physical_action_before_separate_authorization
```

A stop condition does not degrade to a warning. It terminates the preparation transaction and preserves the relevant evidence for review.

## Public carrier

The canonical public carrier contains one manifest and five measured members:

```text
MANIFEST.json

PREFLIGHT/
  preparation-state.json
  decision.json

PUBLIC/
  status.json

RECOVERY/
  profile.json
  verify_preflight.py
```

The carrier contains only the initial `PREPARED_NOT_ARMED` state. It does not contain private coordinate headers or a compiled card. Those belong to a later private preparation transaction. The manifest closes the source graph, issue #37, profile digest, verifier digest, complete five-file denominator, terminal, and every non-claim.

Unmanifested files, missing members, symlink members, changed bytes, changed rows, altered state, altered decision, altered public status, changed profile, changed terminal, changed non-claims, or changed carrier identity refuse.

## External verifier authentication

The carrier embeds a standard-library verifier under `RECOVERY/verify_preflight.py`. Direct execution reconstructs the canonical prepared state, decision, public status, file denominator, manifest, and carrier identity, while truthfully reporting that it has not authenticated itself.

The external bootstrap reads and hashes the embedded verifier once, then executes those exact measured bytes through a trusted isolated stdin launcher rather than reopening the carrier pathname. It invokes the measured verifier without an authentication channel or output path, requires one canonical direct `PASS` receipt with `bootstrapAuthenticated: false`, validates every physical and authority non-claim, and then constructs the authenticated receipt itself. The admitted verifier digest is:

```text
c483507c0246fdcc502e21f60937f0ff81df020871120ab56abd619131ef49d2
```

A substituted verifier is refused before its bytes run. Direct refusal remains canonical and unauthenticated even when a caller forges legacy environment variables. Verdict output inside the measured carrier, hard-linked to a measured member, or resolved anywhere under the repository root is refused before mutation.

## Commands

From the repository root:

```powershell
$Tool = 'mating_surface\anchor_node\axm-head-physical-flight-preflight-review-card-01.ps1'
$Profile = 'mating_surface\anchor_node\axm-head-physical-flight-preflight-review-card-01-profile.json'
$Prepared = Join-Path $env:TEMP 'axm-head-preflight-review-card-01-prepared.json'
$Carrier = Join-Path $env:TEMP 'axm-head-preflight-review-card-01-carrier'
$Verdict = Join-Path $env:TEMP 'axm-head-preflight-review-card-01-verdict.json'

& $Tool validate-profile $Profile
& $Tool prepared-state $Profile --out $Prepared
& $Tool evaluate $Profile $Prepared
& $Tool build-carrier $Profile --out $Carrier
& $Tool verify-carrier $Carrier --out $Verdict
```

The prepared state and carrier must terminate `PREPARED_NOT_ARMED`, with physical authorization false, physical execution false, mission-volume materialization false, workers zero, listeners zero, and authority `none`.

A private orchestration process may later construct a state containing only the exact checkout bindings and four body-free content headers, then run:

```powershell
& $Tool compile-card $Profile PRIVATE_BODY_FREE_STATE.json --out PRIVATE_REVIEW_STATE.json
& $Tool evaluate $Profile PRIVATE_REVIEW_STATE.json
```

A successful result is `READY_FOR_HUMAN_REVIEW`, not authorization. The private state remains outside the repository.

## Qualification and hostile witnesses

The focused suite contains forty-nine permanent witnesses. It proves the exact source graph, canonical profile digest, issue #37 binding, twelve-phase denominator, sixteen-stage packet denominator, prepared zero-activity state, all four terminals, exact checkout requirements, four-header privacy denominator, deterministic card compilation, unauthorized action state, receipt and stop closure, deterministic carrier bytes, direct-verifier honesty, external verifier authentication, and the closed five-member carrier.

Hostile witnesses refuse source drift, dirty or moving checkouts, missing headers, symlink roots, duplicate labels, invalid content references, physical execution, worker or listener activity, authority promotion, forged cards, unmanifested files, missing files, re-signed public claim promotion, re-signed preparation activity, Boolean/integer JSON type confusion after complete re-signing in both carrier and private review-card semantics, issue-number type confusion, forged bootstrap environment variables, non-canonical direct refusal, repository-local builder, bootstrap, and direct-verifier output in both live checkouts and exact Git-blob materializations, canonical carrier-I/O race refusal, rewritten profile provenance, malicious verifier substitution, post-measurement verifier-path replacement, verdict output overlap, hard-link aliasing, and symlink members.

The workflow qualifies both the exact pull-request head and GitHub's synthesized merge coordinate on Ubuntu and Windows, replays the inherited AXM HEAD and flight-conductor suites, validates the PowerShell surface, and compares the canonical prepared carrier, public status, and authenticated verdict bytes across platforms and coordinates.

## Relationship to issue #37

Issue #37 remains the sole private physical-flight ledger. This preflight review-card contract does not initialize or update that ledger. It does not satisfy any `private_local_attested` gate, packet stage, physical cell, successor, or sealed-flight criterion. The preflight review-card contract makes the body-free private preparation and review card mechanically constructible against the admitted supplier floor.

Only a later, separately reviewed private authorization transaction may accept one bounded action under issue #37. That transaction must preserve the exact source graph, named-human authority, resident-floor continuity, optional HALO3 semantics, HUMAN_REQUIRED reunion, cold successor, private evidence custody, and every public non-claim.

## Claim boundary

This candidate proves a public physical-flight preflight review-card contract, exact admitted supplier and conductor binding, frozen physical-floor binding, sole-ledger binding, closed body-free private-coordinate schema, deterministic unauthorized operator review card, independently reconstructed prepared carrier, and externally authenticated verification.

It does not prove that a private workstation exists, equipment was observed, any physical coordinate was accessed, a mission volume was materialized, a worker or listener ran, a task executed, a model output was correct, issue #37 advanced, the physical Estate was qualified, or any representative-operator, field-network, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons qualification or authority exists.

## Control question

Does the preflight review-card contract let a foreign successor reconstruct the exact supplier, conductor, physical floor, issue, private-coordinate denominator, phase plan, stop conditions, and review card while proving that every listed action remains unauthorized and that the named human has nothing to do at the Estate until a separate private authorization transaction produces one exact bounded action?
