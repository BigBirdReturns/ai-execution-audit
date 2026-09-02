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

## The declared source components

```text
stc_mary_successor_flight_law.py               shared construction law (producers only)
invoke_stc_mary_successor_packet_source.py     measured closed-role execution launcher
invoke_stc_mary_successor_packet_source_bootstrap.py external launcher measurement boundary
stc_mary_successor_packet_compiler.py          0.2 compiler and materializer
stc_mary_successor_packet_runtime.py           0.2 packet runtime
stc_mary_successor_packet_orchestrator.py      admission-driven recording orchestrator
verify_stc_mary_successor_evidence_materialization.py  admitted-role to packet-body bridge
verify_stc_mary_successor_execution_receipt.py independent final execution-receipt verifier
verify_stc_mary_successor_packet.py            independent successor packet verifier
verify_stc_mary_successor_packet_bootstrap.py  measured-source bootstrap
verify_stc_mary_successor_source_admission.py  exact commit/tree/blob source verifier
verify_stc_mary_successor_source_admission_bootstrap.py external measured verifier bootstrap
verify_stc_mary_successor_pre_seal_closure.py  pre-seal closure verifier
stc_mary_successor_seal_adapter.py             sealing and detached verification
verify_stc_mary_successor_post_seal_closure.py post-seal closure verifier
stc-mary-successor-packet-flight-01.ps1        operator entrypoint
STC-MARY-SUCCESSOR-PACKET-FLIGHT-01.md         this runbook
stc-mary-successor-packet-flight-01-profile-01.json   the profile
conformance/test_stc_mary_successor_packet_flight_01.py   the witness denominator
.github/workflows/stc-mary-successor-packet-flight-01.yml pinned hosted qualification
```

The independent verifiers import **nothing** from the shared law module. Each re-implements
canonical JSON, content identity, bounded reads and source-set measurement, so a defect in
the construction law cannot authenticate the objects that law produced.

## Exact Git-blob source admission

Compilation never reads a successor source member from the ambient checkout. Before a
packet can exist, the external source bootstrap reads the source-admission verifier itself
from one exact full Git commit, executes those measured bytes under `python -I -S -B` from a
foreign temporary directory, and emits a content-addressed receipt. The receipt binds the
commit, tree, profile blob and canonical profile digest, then binds every declared member's
repository path, packet path, Git blob, SHA-256 and byte count. Its derived
`successorSourceSetId` uses the packet-relative member order that the packet verifier
reproduces.

The direct verifier always reports `bootstrapAuthenticated: false`. Only the external
measured bootstrap may change that field, after proving its executed verifier digest and
blob identity equal the verifier row the exact commit declared. The compiler authenticates
the complete receipt, replays every Git object lookup, copies only `git cat-file blob`
bytes, writes the canonical receipt to `lineage/SOURCE-ADMISSION.json`, and requires the
packet-carried source set to reproduce the admitted identity. Working-tree mutation,
including CRLF checkout conversion, is outside the source identity.

## Packet-carried execution custody

The PowerShell entrypoint calls an external bootstrap, never the ambient launcher. For
`compile`, that bootstrap obtains the launcher from the exact admitted Git object,
measures its Git blob, SHA-256, and byte count, and executes only those measured bytes.
For every packet operation it first reproduces all twenty packet-carried members,
requires exact equality with `lineage/SOURCE-ADMISSION.json` and
`lineage/SUCCESSOR-SOURCE-SET.json`, measures the carried launcher, and executes only
those bytes. Editing only the ambient repository launcher therefore has no effect.

The measured launcher executes every selected module under `python -I -S -B`, from a
foreign working directory and a scrubbed environment. Its content-addressed receipt
permanently records `isolated = 1`, `noSite = 1`, `dontWriteBytecode = 1`, and
`ambientRepositorySourceTrusted: false`. The independently measured receipt verifier
consumes that false value and binds the source admission, commit, tree, Git object format,
complete source-set identity, packet identity, exact role/module member, Git blob,
SHA-256, process terminal, and authority `none`.

The final public role map contains exactly: `compile`, `verify-packet`,
`verify-evidence-materialization`, `materialize-or-resume`, `record-or-resume`,
`close-pre-seal`, `seal-or-resume`, `verify-detached`, `close-post-seal`, and `status`.
Verification and mutation are distinct roles even when one admitted module implements
both modes.

## The forty-three admitted roles reach the packet, or nothing does

The admitted gate decides that forty-three exact evidence bodies are admissible and
publishes a per-stage evidence-admission root over them. It then stops: it places no body
anywhere, because a gate that wrote into the packet it judges would be judging its own
work. Nothing previously connected those roles to the files a stage record hashes, so a
packet could carry any non-empty bodies at all while copying the gate's forty-three-role
roots beside them. The seal, the manifest and the detached verification would all agree —
with each other, over a denominator unrelated to the admitted one.

The bridge closes that. It consumes only objects the gate itself identified:

```text
the bootstrap-authenticated ADMISSIBLE_FOR_PACKET_RECORDING receipt
the ADMISSION-REQUEST.json that receipt names by requestId
the candidate evidence workspace the request's body paths resolve inside
the successor packet the roles are destined for
the admitted @2 profile, through this profile's canonical-digest pin
```

and independently replays the mapping: it re-measures every candidate body, recomputes
each body's own content identity, recomputes every stage evidence-admission root and the
complete admission digest root exactly as the gate computes them, and requires all of it
to equal what the receipt published. It then names one deterministic packet coordinate per
role, derived from the admitted evidence role key, so the packet path itself carries role
attribution.

```text
role denominator          43 / 43, 0 extra, 0 missing, 0 duplicate identities
per-body columns          evidenceRole, provenanceClass, evidenceClass, mediaType,
                          bodySchema, bodyContentId, bodySha256, bodyBytes,
                          sourceReceiptId | sourceObservationId, reuseClass,
                          opaqueInstrumentClass, instrumentReceiptId
destination               NN-STAGE/evidence/<evidence-role-key>.json
opaque instrument bodies  two coordinates, the body and its admitted instrument receipt,
                          both counted in physicalBodyCount
statement bindings        stage, sequence, evidenceRole, statementId, bodySha256,
                          nonHumanEvidenceAdmissionRoot, evidenceAdmissionRoot
```

### A role row is receipt-subordinate

Campaign and packet identity are carried once, at receipt level, not repeated on each of
the forty-three rows. Repeating a constant forty-three times adds fields that can drift
without establishing a new predicate. What makes receipt-level binding sufficient is that
each of the following is independently enforced:

```text
receipt identity        recomputed over the complete receipt body
receipt campaignId      equals the successor contract campaignId
receipt packetId        equals the packet marker and state
each candidate body     independently parsed, identity recomputed, and its own
                        campaignId, packetId, stage, sequence, evidenceRole and
                        provenanceClass checked against the transaction
each row                accepted only as a member of the authenticated parent receipt
each row sequence       equals the admitted sequence of the stage it names
stage root              reconstructed from the complete admitted row set, before any
                        stage is recorded
packet-side body        re-read and compared with its exact row at recording time
```

The profile classifies the row schema as `receipt-subordinate`, and every surface that
reads rows requires that classification before it reads one. No runtime, verifier or
closure surface accepts a detached row.

```text
row lifted out of its receipt          -> MATERIALIZATION_RECEIPT_INVALID
receipt re-signed for another campaign -> MATERIALIZATION_BINDING_INVALID
receipt re-signed for another packet   -> MATERIALIZATION_BINDING_INVALID
row moved to another stage             -> MATERIALIZATION_BINDING_INVALID
row moved to another evidence role     -> STAGE_EVIDENCE_ROOT_MISMATCH
body re-signed for another campaign    -> EVIDENCE_BODY_SUBSTITUTED
body re-signed for another packet      -> EVIDENCE_BODY_SUBSTITUTED
```

Every one of those refuses **before a packet stage is recorded**. Root reconstruction runs
across all sixteen stages ahead of the record loop rather than only inside the recorder, so
a row rebound in stage fourteen cannot let stages one to thirteen be written first.

### The generated coordinates must be portable, not merely locally valid

The packet coordinate derives from the admitted evidence role key, so the admitted profile
decides these paths. Two admitted keys already differ only by stage — `verifier-receipt`
appears in both `RUN_PERSONAL_FLOOR_BASELINE` and `RUN_HALO3_ACCELERATED` — so uniqueness
is proved over the complete stage-scoped destination, not over the key, and under casefold
comparison as well as exactly.

```text
43 generated destinations, 43 exact-unique, 43 casefold-unique
no forbidden character: / \ : * ? " < > |
no parent-directory segment
no leading or trailing whitespace, no trailing dot
no reserved component stem: CON PRN AUX NUL COM1..COM9 LPT1..LPT9
bounded component length and bounded relative-path length
```

A witness enumerates the real admitted denominator and proves the invariant, so a future
role key that collides only by case refuses here rather than on the Windows hosted leg,
half way through materializing a packet.

Downstream, nothing may soften this:

```text
orchestrator   requires the receipt, refuses a stage evidence directory that already
               holds anything, and materializes only the closed set it names
runtime        requires each stage directory to hold exactly those coordinates,
               recomputes each body's content identity from the bytes in the packet,
               and RECONSTRUCTS the stage evidence-admission root from those bodies --
               a stage records only when the reconstructed root equals the authorized one
pre-seal       replays the mapping again, independently of the bridge, and requires
               packet rows == materialization receipt == request and candidate bodies
               == the gate's own stage roots, then recomputes the complete admission root
seal           requires the measured private body count to equal the closure's
```

```text
MATERIALIZATION_RECEIPT_ABSENT | _INVALID       no receipt, or it does not re-identify
MATERIALIZATION_BINDING_INVALID                 it names another admission, request or packet
MATERIALIZATION_ROLE_DENOMINATOR_INVALID        not 43 / 43
ADMISSION_REQUEST_BINDING_INVALID               the request on disk is not the admitted one
EVIDENCE_ROLE_UNADMITTED | _MISSING | _DUPLICATED
EVIDENCE_BODY_SUBSTITUTED                       candidate or packet body is not the admitted one
EVIDENCE_BODY_IDENTITY_FORGED                   the body does not recompute its own identity
STAGE_EVIDENCE_ROOT_MISMATCH                    the root was copied, not reconstructed
ADMISSION_DIGEST_ROOT_MISMATCH                  the complete root does not recompute
PACKET_EVIDENCE_UNMATERIALIZED                  a body nobody admitted is in the packet
```

### The draft no longer describes its own evidence

The `0.2` stage draft has no `evidenceClass` and no `mediaType`. One draft-wide class
cannot truthfully describe `BIND_GRACE`, which combines accepted predecessor receipts with
a named-human statement, and a draft-authored class would have been a second
self-declaration in a schema built to remove the first. Class, media type and provenance
are carried per admitted body and independently verified.

```text
STAGE_DRAFT_DESCRIBES_ITS_OWN_EVIDENCE
```

## What the compiler materializes

```text
PACKET-ROOT.json                               0.2 marker, identity derived not asserted
packet-state.json                              0.2 state, configured, 0 / 16, unsealed
flight-config.json                             canonical mission state carried unchanged
SUCCESSOR-CONTRACT.json                        names all three lineage coordinates
lineage/predecessor-packet/PACKET-ROOT.json    predecessor marker, copied verbatim
lineage/predecessor-packet/packet-state.json   predecessor state, copied verbatim
lineage/PACKET-HANDOFF.json                    binds both packets and both profiles
lineage/SOURCE-ADMISSION.json                  authenticated exact Git-object source receipt
lineage/SUCCESSOR-SOURCE-SET.json              measured over the member bytes below
lineage/successor-source/**                    all twenty source members, verbatim
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

### Source identity is a property of exact Git objects

Authoritative bytes: exact Git objects.

Working-tree bytes: untrusted diagnostic material.

The `successorSourceSetId` is derived from packet-relative paths, SHA-256 digests, and byte
counts of the admitted Git blobs. Checkout line-ending conversion therefore cannot change
it. Ubuntu and Windows, at both exact PR head and synthesized merge, must emit one
parseable `SUCCESSOR_SOURCE_SET_ID` and the aggregation gate requires one identity, one
member denominator, one path set, and one member-digest set. Source-admission receipt IDs
may differ when commit or tree names differ; identical authoritative member blobs must
produce the same successor source-set identity.

## The legal order

```text
1  compile                         configured predecessor -> distinct successor
2  verify-packet                   packet verifier        -> packet verification
3  verify-evidence-materialization bridge verifier        -> verified 43-role mapping
4  materialize-or-resume           bridge mutation        -> 43 packet coordinates
5  record-or-resume                orchestrator           -> 16 stage records
6  close-pre-seal                  closure verifier       -> pre-seal closure
7  seal-or-resume                  seal adapter           -> atomic sealed root
8  verify-detached                 seal adapter           -> detached verification
9  close-post-seal                 closure verifier       -> post-seal closure
10 status                          packet runtime          -> terminal status
```

Evidence admission and named-human authentication occur between roles 2 and 3. They are
separately admitted production boundaries, not extra roles in this ten-role source map.

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

**The statement of each stage is now derived, not guessed.** The admission receipt
publishes each stage's admitted evidence identities but does not mark which of them is the
named-human statement, so stage membership alone proved only that an identity belonged to
the stage — it could equally have been that stage's accepted receipt or current
observation. The materialization bridge derives the exact statement from the admitted
provenance class of each role and publishes one binding per statement-owing stage:

```text
stage, sequence, evidenceRole, statementId, bodySha256,
nonHumanEvidenceAdmissionRoot, evidenceAdmissionRoot
```

The orchestrator and the pre-seal closure both require the authenticated statement
identities to be exactly those three, each on its own stage and its own named-human role.
No `@3` profile change was needed: the request the gate identified and the candidate
bodies it measured are enough to recover the provenance the receipt does not publish.

Issue #94's future receipt should authenticate those exact bindings, and the sixteen exact
confirmation bindings, rather than a flat set of three identities.

The only mechanism this source set can exercise is the synthetic fixture, which
authenticates nobody and is refused against any campaign label without the `SYNTHETIC-`
prefix. Real Campaign A application stays held until #94 admits a mechanism.

## Pre-seal closure binds only pre-seal facts

```text
forty-three admitted evidence roles, re-measured in the candidate workspace and again
    in the packet, and required to be the same bytes in both
one exact evidence-materialization receipt, re-identified and bound to the request
every stage evidence-admission root, recomputed from the bodies the packet carries
the complete evidence-admission digest root, recomputed from those stage roots
three authenticated named-human statement identities, on an exact stage and role
sixteen authenticated stage-confirmation identities
final packet-stage record identity root
pre-seal evidence-manifest root, re-hashed from the bodies on disk and carrying role
    and provenance per body
retained two-branch HUMAN_REQUIRED conflict
unsealed packet state
absent sealed root
authority none
```

The closure replays the admitted mapping itself rather than trusting the bridge that
produced the receipt, so a body quietly replaced in the packet refuses as
`EVIDENCE_BODY_SUBSTITUTED` against the candidate the gate admitted — a stronger statement
than drift against the record's own digest, which the runtime's custody check still makes
separately.

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
.\stc-mary-successor-packet-flight-01.ps1 admit-source    -SourceCommit <full-sha> -Out <source-admission>
.\stc-mary-successor-packet-flight-01.ps1 compile         -Workstation <dir> -Predecessor <dir> -Packet <dir> -SourceAdmissionReceipt <source-admission> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 verify-packet   -Packet <dir> -Out <verdict>
.\stc-mary-successor-packet-flight-01.ps1 verify-evidence-materialization -Packet <dir> -AdmissionReceipt <file> -Candidates <dir> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 materialize-or-resume -Packet <dir> -AdmissionReceipt <file> -Candidates <dir> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 record-or-resume -Packet <dir> -AdmissionReceipt <file> -MaterializationReceipt <file> -AuthenticationReceipt <file> -Candidates <dir> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 close-pre-seal  -Packet <dir> -AdmissionReceipt <file> -MaterializationReceipt <file> -AuthenticationReceipt <file> -Candidates <dir> -Out <closure>
.\stc-mary-successor-packet-flight-01.ps1 seal-or-resume  -Packet <dir> -Sealed <dir> -PreSealClosure <file> -Out <receipt>
.\stc-mary-successor-packet-flight-01.ps1 verify-detached -Packet <dir> -Sealed <dir> -Out <verification>
.\stc-mary-successor-packet-flight-01.ps1 close-post-seal -Packet <dir> -Sealed <dir> -PreSealClosure <file> -DetachedVerification <file> -Out <closure>
.\stc-mary-successor-packet-flight-01.ps1 status           -Packet <dir> -Out <status>
```

`admit-source` and `verify-packet` always run through their respective bootstraps. Neither
verifier can authenticate itself; each
reports `bootstrapAuthenticated: false` on any direct run, by design.
For packet operations, `-ExecutionReceipt <file>` may be supplied explicitly; when
`-Out` is present the wrapper otherwise writes `<Out>.execution-receipt.json`.

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
