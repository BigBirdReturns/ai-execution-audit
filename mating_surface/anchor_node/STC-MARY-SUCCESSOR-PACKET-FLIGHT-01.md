# STC MARY successor packet flight 01

## What this object is

A **source-only construction and qualification set** for one
`stc-mary/private-flight-packet/0.2` successor packet.

It compiles a successor from a synthetic configured `0.1` predecessor, records that
successor only from evidence somebody else already admitted, closes it before and after
sealing, and qualifies the whole legal order over synthetic fixtures.

It applies to no live campaign. It authenticates no human principal. It mutates no
predecessor packet. Campaign A remains at `10 / 2 / 0`, configured `0.1`, `0 / 16`
recorded stages, authority `none`.

## Why it exists

The admitted `stc-mary/packet-evidence-admission@2` gate decides whether proposed private
evidence *may* be recorded. It deliberately stops there: it never calls a recorder, never
records a stage, and never sets a confirmation. Something has to carry an
`ADMISSIBLE_FOR_PACKET_RECORDING` verdict into an actual packet, and that something did
not exist.

It could not be the frozen `0.1` runtime. That runtime records a stage when the
operator-authored draft carries `operatorConfirmed: true` — a Boolean the operator process
writes about itself — and its Stage 16 observation contract requires
`publicDispositionBodyFree: true`, an assertion about a public disposition the sealer
cannot create until all sixteen stages are already recorded. Admission `@2` repaired the
*contract* by targeting a successor packet. This source set builds the successor.

## The boundary this source set does not cross

```text
frozen packet runtime         never imported, never modified
admitted admission profile    pinned by canonical digest, never modified
predecessor packet            read, fenced, never written
live campaign                 held; every fixture carries the SYNTHETIC- prefix
human principal               not authenticated here; issue #94 owns the mechanism
```

## The admitted law is bound, not copied

This profile does **not** restate the Stage 16 decision surface. It binds the admitted
profile by canonical digest and reads the surface from it:

```text
admission profile     stc-mary/packet-evidence-admission@2
canonical SHA-256     0296e23f4ac15deb933420c5ff7121be3904add565b39bdc91808e0d8ded1f6d

derived from it, never restated here:
  stageSequence
  stages[*].requiredTerminal
  stages[*].controlQuestion
  stages[*].observation
  stages[*].evidenceRoles
  denominator
```

A successor packet therefore cannot carry a Stage 16 contract the admission gate never
admitted. Editing the admitted profile breaks every surface in this set at once, which is
the intended blast radius.

## The ten members

```text
stc_mary_successor_flight_law.py               shared construction law (producers only)
stc_mary_successor_packet_compiler.py          0.2 compiler and materializer
stc_mary_successor_packet_runtime.py           0.2 packet runtime
stc_mary_successor_packet_orchestrator.py      admission-driven recording orchestrator
verify_stc_mary_successor_packet.py            independent successor packet verifier
verify_stc_mary_successor_packet_bootstrap.py  measured-source bootstrap
verify_stc_mary_successor_pre_seal_closure.py  pre-seal closure verifier
stc_mary_successor_seal_adapter.py             sealing and detached verification
verify_stc_mary_successor_post_seal_closure.py post-seal closure verifier
stc-mary-successor-packet-flight-01.ps1        operator entrypoint
STC-MARY-SUCCESSOR-PACKET-FLIGHT-01.md         this runbook
stc-mary-successor-packet-flight-01-profile-01.json   the profile
conformance/test_stc_mary_successor_packet_flight_01.py   the witness denominator
.github/workflows/stc-mary-successor-packet-flight-01.yml pinned hosted qualification
```

The three verifiers import **nothing** from the shared law module. Each re-implements
canonical JSON, content identity, bounded reads and source-set measurement, so a defect in
the construction law cannot authenticate the objects that law produced.

## What the compiler materializes

```text
PACKET-ROOT.json                               0.2 marker, identity derived not asserted
packet-state.json                              0.2 state, configured, 0 / 16, unsealed
flight-config.json                             canonical mission state carried unchanged
SUCCESSOR-CONTRACT.json                        names all three lineage coordinates
lineage/predecessor-packet/PACKET-ROOT.json    predecessor marker, copied verbatim
lineage/predecessor-packet/packet-state.json   predecessor state, copied verbatim
lineage/PACKET-HANDOFF.json                    binds both packets and both profiles
lineage/SUCCESSOR-SOURCE-SET.json              measured over the member bytes below
lineage/successor-source/**                    all fourteen source members, verbatim
NN-STAGE/evidence/                             the empty stage skeleton
```

The packet carries the exact bytes of the runtime that will record it. That is what the
admitted gate re-measures before it admits any evidence for the packet.

### The predecessor is proved unmoved

The compiler fences every regular file under the predecessor before and after
materialization and refuses on any difference:

```text
PREDECESSOR_MUTATED_DURING_COMPILATION
```

### The source-set identity is a property of the checkout

Members are copied byte for byte rather than normalized, so a working tree with different
line endings produces a different `successorSourceSetId`. That is the honest reading: a
different checkout is a different source set. Do not pin the measured identity across
platforms; pin the members.

## The legal order

```text
1  compile           configured 0.1 predecessor        -> distinct 0.2 successor
2  verify            measured-source bootstrap         -> successor packet verification
3  admit             admitted @2 gate + its bootstrap  -> ADMISSIBLE_FOR_PACKET_RECORDING
4  authenticate      issue #94 mechanism               -> authentication verification
5  record            orchestrator                      -> 16 stage records, in order
6  close pre-seal    pre-seal closure verifier         -> pre-seal closure
7  seal              seal adapter                      -> sealed root
8  verify detached   seal adapter                      -> detached verification
9  close post-seal   post-seal closure verifier        -> post-seal closure
```

Step 3 is **not** part of this source set. Evidence admission belongs to the separately
admitted gate in production. Run it yourself and hand its bootstrap-authenticated receipt
to the orchestrator.

## Recording consent has exactly one channel

The `0.2` stage draft schema has **no `operatorConfirmed` field at all**. A draft cannot
offer one without failing its exact key denominator. A stage becomes recordable only when:

```text
the draft names a stageConfirmationId
                and
the orchestrator supplies the matching recording authorization, derived from
  the admitted receipt's exact stage decision for that stage
```

The authorization binds the stage's evidence-admission root, observation digest and
required terminal. A draft may agree with it. A draft may not supply it.

```text
draft carrying operatorConfirmed        -> STAGE_DRAFT_SELF_CONFIRMED
draft naming another confirmation       -> STAGE_CONFIRMATION_BINDING_INVALID
draft observation the human never saw   -> STAGE_OBSERVATION_BINDING_INVALID
stage out of sequence                   -> STAGE_OUT_OF_ORDER
```

## The admission receipt must be externally bootstrap-authenticated

The orchestrator refuses a receipt the gate signed for itself:

```text
bootstrapAuthenticated must be true
bootstrapVerifierSha256 must equal measuredVerifierSha256
admissionId must recompute over the body the gate signed, with the four
  bootstrap annotations removed
```

It then requires the receipt to bind this exact packet, campaign, canonical mission state,
successor contract, source set, handoff and predecessor, at the complete `43 / 40 / 3`
evidence denominator with sixteen exact `RECORD_STAGE` decisions against final roots.

## The closed interface issue #94 must satisfy

The orchestrator will not read `authenticationBinding` text or `actorClass` text as proof
that a human acted. Both are supplied by the same body that declares them; a machine can
write either. It requires a separate receipt:

```text
schema        stc-mary/named-human-authentication-verification/1
binds         admissionId, packetId, campaignId
names         statementIds        exactly three, one per statement-owing stage
              confirmationIds     exactly the sixteen stage confirmations
              authenticatedStatementIds  equal to statementIds
declares      principalClass      named_human
              mechanismId         the mechanism that actually verified them
```

```text
absent            -> HUMAN_AUTHENTICATION_RECEIPT_ABSENT
not bound         -> HUMAN_AUTHENTICATION_BINDING_INVALID
short denominator -> HUMAN_AUTHENTICATION_DENOMINATOR_INCOMPLETE
synthetic on live -> SYNTHETIC_AUTHENTICATION_APPLIED_TO_LIVE_CAMPAIGN
```

**A known boundary.** The admission receipt publishes each stage's admitted evidence
identities but does not mark which of them is the named-human statement. The orchestrator
therefore requires each authenticated statement identity to be one the gate admitted for a
distinct statement-owing stage, and relies on the authentication mechanism to have picked
the right one. Distinguishing them mechanically would require the admission gate to
publish provenance per identity — a candidate for `@3`, not something this source set may
add to a profile it is bound to by digest.

The only mechanism this source set can exercise is the synthetic fixture, which
authenticates nobody and is refused against any campaign label without the `SYNTHETIC-`
prefix. Real Campaign A application stays held until #94 admits a mechanism.

## Pre-seal closure binds only pre-seal facts

```text
three authenticated named-human statement identities
sixteen authenticated stage-confirmation identities
final packet-stage record identity root
complete evidence-admission digest root
pre-seal evidence-manifest root, re-hashed from the bodies on disk
retained two-branch HUMAN_REQUIRED conflict
unsealed packet state
absent sealed root
authority none
```

A scan refuses any post-seal field appearing in the pre-seal object at all:

```text
POST_SEAL_ASSERTION_BEFORE_SEALING
```

Neither closure writes into the packet. Both emit their receipt outside every surface they
measured, exactly as the admitted admission gate emits its own.

## Post-seal closure is the only surface that may assert the sealed facts

```text
sealed run present
public disposition present
public disposition body-free
sealed manifest valid
detached verification PASS
public evidence bodies 0
private physical flight complete
all stronger qualifications false
```

It asserts them from measurement: it re-reads the sealed directory, re-hashes every
manifest entry, and requires the supplied detached verification to be byte-identical to
the one the sealed directory carries and reproducible from the sealed run alone.

**Completion is not qualification.** A completed local private physical flight leaves
every stronger qualification false, and the closure refuses if any of them is claimed:

```text
STRONGER_QUALIFICATION_CLAIMED
```

## The qualifying witness

One executable witness drives the entire order from a configured predecessor at zero of
sixteen. Constructing the completed final state directly proves nothing about order and is
not an admitted witness.

```powershell
.\stc-mary-successor-packet-flight-01.ps1 qualify
```

or directly:

```text
python -m unittest discover -s mating_surface/anchor_node/conformance \
  -p 'test_stc_mary_successor_packet_flight_01.py'
```

The hosted gate pins the exact witness count and fails on a bare `OK` that ran a different
number of witnesses, on any skip, and on any drift in the pinned admitted profile digest.

## Operator commands

```powershell
.\stc-mary-successor-packet-flight-01.ps1 compile         -Workstation <dir> -Predecessor <dir> -Packet <dir> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 verify          -Packet <dir> -Out <verdict>
.\stc-mary-successor-packet-flight-01.ps1 record          -Packet <dir> -AdmissionReceipt <file> -AuthenticationReceipt <file> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 close-pre-seal  -Packet <dir> -AdmissionReceipt <file> -AuthenticationReceipt <file> -Out <closure>
.\stc-mary-successor-packet-flight-01.ps1 seal            -Packet <dir> -Sealed <dir> -PreSealClosure <file> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 verify-detached -Sealed <dir> -Out <verification>
.\stc-mary-successor-packet-flight-01.ps1 close-post-seal -Packet <dir> -Sealed <dir> -PreSealClosure <file> -DetachedVerification <file> -Out <closure>
```

`verify` always runs through the bootstrap. The verifier cannot authenticate itself and
reports `bootstrapAuthenticated: false` on any direct run, by design.

## Stop wall

```text
Campaign A                 10 CLOSED / 2 HOLD / 0 REFUSED
frozen packet              configured 0.1
recorded stages            0 / 16
stage evidence             0
human statements           0
stage confirmations        0
successor packet           absent
sealed root                absent
private flight complete    false
authority                  none
```

No current observation, human statement, stage confirmation, packet mutation, stage
recording or sealing against Campaign A is authorized by this transaction.
