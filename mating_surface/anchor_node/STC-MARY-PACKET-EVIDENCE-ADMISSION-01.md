# STC MARY packet evidence admission 01

## What this object is

A **source-authenticated pre-record admission gate** for one already configured,
still unrecorded private-flight packet.

It is not the packet recorder. It is not a repaired packet recorder. It never records
a stage, never sets `operatorConfirmed`, never signs a named-human statement, and never
issues a stage confirmation.

## Why it exists

The admitted packet recorder authenticates the operator's own Boolean, not the
evidence. To record a stage it requires:

```text
operatorConfirmed === true
evidenceClass in {private_local_attestation, private_instrument_receipt, private_operator_statement}
mediaType       a bounded string
evidence/       1..64 regular non-empty files, each <= 8 GiB
```

It then hashes those bytes and copies `evidenceClass` and `mediaType` **from the
operator-authored draft**. It does not validate the body's schema, self-identity,
provenance, campaign binding, stage relevance, or whether the body proves the claimed
observation.

Content addressing therefore proves one thing only: the chosen bytes did not change
*after* recording. It proves nothing about what the bytes *are*.

Campaign A ships a 133-byte `stc-mary-private-evidence-envelope-template/1` in its own
products. That untouched template is a structurally valid, non-empty file, so it
satisfies every mechanical check the recorder makes. A manufactured packet denominator
is already within reach of the admitted runtime.

This gate closes that hole **ahead of** the recorder, additively, without patching it.
The future-runtime repair that binds admission and named-human confirmation *inside*
recording is a separate transaction against a separate issue and branch, so that the
future source repair can never become the evidence that admits a frozen campaign.

## The two denominators

The forty-three evidence roles and the sixteen stage confirmations are different
denominators and this object never collapses one into the other.

```text
evidence roles                          43
  machine-verifiable or freshly observable 41
  substantive named-human statements        2

stage-confirmation decisions            16
```

The two statement bodies supply campaign substance. The sixteen confirmations answer
whether each exact stage observation and admitted evidence set may be recorded.
Neither is reducible to one Boolean written by an operator process.

## The closed evidence matrix

Carried by the admitted profile, not hardcoded in the gate:

```text
READY_FROM_ACCEPTED_RECEIPTS          7
REQUIRES_CURRENT_LOCAL_OBSERVATION    7
REQUIRES_HUMAN_STATEMENT              2
MISSING_HISTORICAL_PHYSICAL_EVIDENCE  0
REFUSED_AS_UNRECOVERABLE              0
```

```text
01 VERIFY_INPUTS                      READY_FROM_ACCEPTED_RECEIPTS          2 roles
02 MOUNT_PERSONAL_FLOOR               READY_FROM_ACCEPTED_RECEIPTS          2 roles
03 BIND_GRACE                         REQUIRES_HUMAN_STATEMENT              2 roles
04 RUN_PERSONAL_FLOOR_BASELINE        READY_FROM_ACCEPTED_RECEIPTS          3 roles
05 ATTACH_HALO3                       REQUIRES_CURRENT_LOCAL_OBSERVATION    3 roles
06 RUN_HALO3_ACCELERATED              READY_FROM_ACCEPTED_RECEIPTS          4 roles
07 REMOVE_HALO3                       REQUIRES_CURRENT_LOCAL_OBSERVATION    2 roles
08 VERIFY_PERSONAL_FLOOR_CONTINUITY   READY_FROM_ACCEPTED_RECEIPTS          3 roles
09 REMOVE_LATTICE                     REQUIRES_CURRENT_LOCAL_OBSERVATION    2 roles
10 VERIFY_LOCAL_CONTINUITY            REQUIRES_CURRENT_LOCAL_OBSERVATION    2 roles
11 PARTITION_TWO_CELLS                READY_FROM_ACCEPTED_RECEIPTS          3 roles
12 RESTORE_LINK_HOLD_CONFLICT         REQUIRES_HUMAN_STATEMENT              3 roles
13 REPLACE_HEAD                       READY_FROM_ACCEPTED_RECEIPTS          3 roles
14 REBUILD_PROJECTIONS                REQUIRES_CURRENT_LOCAL_OBSERVATION    3 roles
15 COLD_SUCCESSOR_VERIFY              REQUIRES_CURRENT_LOCAL_OBSERVATION    3 roles
16 SEAL_PRIVATE_EVIDENCE              REQUIRES_CURRENT_LOCAL_OBSERVATION    3 roles
```

Every role name is the exact string the frozen packet profile already declares under
that stage's `requiredEvidence`. The gate adds, per role, a provenance class and a
closed set of semantic predicates the body must prove.

## What the gate actually does to a body

For each proposed evidence body it independently:

```text
reads the bytes under a bounded, symlink-refusing allocation
measures SHA-256 and byte count, and refuses if the descriptor disagrees
parses the recognized JSON schema and exact-key validates it
recomputes the content identity from the body and refuses a forged one
binds campaign, packet, stage, sequence, evidence role, canonical mission state
requires the exact semantic predicate denominator that role owes the stage
```

`evidenceClass` and `mediaType` are **checked against the body's provenance class**,
not copied from the descriptor. An operator may not assert that a current observation
is an operator statement.

Opaque instrument bodies are supported, but never on the operator's word: the body must
be accompanied by an admitted `stc-mary/packet-evidence-instrument-receipt/1` that binds
the measured opaque digest, byte count, instrument class, stage, role, campaign, packet,
and the current observation transaction. An opaque body inherits nothing from a draft
string.

No two roles may share an evidence identity or the same body bytes. One blob is not a
denominator.

## Reused predecessor receipts

A predecessor receipt is admitted only as:

```text
reuseClass: reused_pre_stage_receipt
```

and only when its schema and content identity verify, it belongs to Campaign A, its
`acceptedPredecessorCoordinate` is in the request's accepted predecessor graph, its
`sourceReceiptId` is in that coordinate, and it **predates** the current observation
transaction. A receipt that backdates itself into the observation window is refused as
misrepresented-as-fresh. The receipt is never serialized as though it were captured
during the packet stage.

## Current local observations

A current observation must name the declared observation transaction, be captured
inside its bounded window, and carry `claimsHistoricalTransition: false`. It proves
only what is observable now. It cannot reconstruct a transition that was never
measured — attachment, removal, Lattice absence, projection rebuild, cold-start
reconstruction, and the pre-seal denominator are all held to that rule.

## Named-human statements

The gate prepares the two statement forms. It cannot sign them.

```text
requiredActorClass:   named_human
forbiddenActorClasses: agent, automation, machine, model, packet_runner, scheduler, tool, verifier
```

A statement may accept only evidence identities this gate actually admitted for the
statement's own stage, and its `terminalOrRetainedObligation` must equal the stage's
required terminal.

`RESTORE_LINK_HOLD_CONFLICT` additionally requires:

```text
retainedBranches:  two distinct branch digests
selectedWinner:    null
automaticMerge:    false
terminal:          HUMAN_REQUIRED
```

## Sixteen exact stage confirmations

Every stage requires a separately authenticated named-human confirmation bound to that
stage's evidence-admission root and observation digest. A partial set is not a
denominator; a replayed confirmation is refused; a confirmation bound to another root,
observation, campaign, packet, stage, or terminal is refused.

A bounded batch confirmation may accompany the sixteen exact decisions. It may not
replace them, and it must exact-enumerate every stage with matching roots, digests,
terminals, and decisions. An unbounded blanket approval is refused.

At `READY_FOR_NAMED_HUMAN_DECISION` the two statement-owing stages report
`evidenceAdmissionRootFinal: false`, so a confirmation is never invited against a root
that has not settled. The statement forms bind the stable
`nonHumanEvidenceAdmissionRoot` instead.

## Terminal

```text
READY_FOR_NAMED_HUMAN_DECISION
ADMISSIBLE_FOR_PACKET_RECORDING
HOLD
REFUSED
```

`READY_FOR_NAMED_HUMAN_DECISION`

```text
all 41 non-human evidence roles independently verified
two human-statement requirements prepared, unsupplied
sixteen stage-confirmation records prepared, unsupplied
packetStagesRecorded: 0
operatorConfirmedFlagsSet: 0
authority: none
```

`ADMISSIBLE_FOR_PACKET_RECORDING`

```text
all 43 evidence roles independently verified, including both statements
sixteen stage confirmations authenticated and exact-bound, all RECORD_STAGE
no missing or duplicate evidence role
one complete evidence-admission digest root
packetStagesRecorded: 0
operatorConfirmedFlagsSet: 0
authority: none
```

`HOLD` is reached when a non-human role is outstanding, when the statements are in but
the sixteen decisions are not, or when the named human held one or more stage
decisions. `REFUSED` covers every source defect and a named-human `REFUSE_STAGE`.

**Even `ADMISSIBLE_FOR_PACKET_RECORDING` records nothing.** A later, separately
authorized wrapper may invoke the frozen recorder one stage at a time, and only while
re-checking that each stage still matches the admitted evidence and confirmation roots.

## What it refuses to do

```text
call the packet recorder                  -> never
set operatorConfirmed                     -> never
record a packet stage                     -> never
sign or generate a human statement        -> never
issue a stage confirmation                -> never
write anything into the packet            -> never
read an evidence body into public output  -> never
grant any qualification or authority      -> never
```

This is fenced, not merely conventional. The gate digests the packet marker, packet
state, packet configuration, and workstation marker before and after the run and
refuses with `PACKET_MUTATED_DURING_ADMISSION` if any fence moves. It refuses to run at
all against a packet that is unconfigured, already sealed, or already carrying a
recorded stage. CI additionally refuses any admission source member that names the
frozen recorder module or emits its operator Boolean.

## Bootstrap authentication

Called directly, the gate reports `bootstrapAuthenticated: false` and is structurally
incapable of setting that flag itself.

The external bootstrap measures the frozen gate bytes, executes the measured copy in an
isolated interpreter (`-I -S`) from a foreign temporary directory, validates the direct
receipt — including that the gate bound the *stored* admission source member to the
bytes that actually executed, that the terminal is inside the admitted denominator, and
that the run recorded no stage, set no confirmation flag, invoked no recorder, mutated
no packet byte, and manufactured no human decision — and only then sets
`bootstrapAuthenticated: true`.

## Operator lanes

```powershell
# canonical: measured, isolated, bootstrap-authenticated
.\stc-mary-packet-evidence-admission.ps1 bootstrap-admit `
  --workstation <frozen workstation root> `
  --packet      <configured packet root> `
  --candidates  <admission workspace, outside the packet> `
  --out         <receipt outside every measured surface>

# direct, not bootstrap-authenticated
.\stc-mary-packet-evidence-admission.ps1 admit --workstation ... --packet ... --candidates ...

# admission helpers
.\stc-mary-packet-evidence-admission.ps1 profile-digest
.\stc-mary-packet-evidence-admission.ps1 source-set
.\stc-mary-packet-evidence-admission.ps1 denominator
```

The admission workspace must be outside the packet and outside this repository. The
receipt is body-free and carries no path, host, credential, evidence filename, or
evidence body, and it may be written only outside the packet and the workspace.

## Admission workspace shape

```text
<workspace>/
  ADMISSION-REQUEST.json
  bodies/<NN>-<STAGE>/<evidence-role-key>.json
  bodies/<NN>-<STAGE>/<evidence-role-key>.bin          (opaque instrument body)
  bodies/<NN>-<STAGE>/<evidence-role-key>-receipt.json (its instrument receipt)
```

Run `denominator` to print the exact sixteen-stage, forty-three-role contract, with the
required provenance class and semantic predicates per role, and no campaign coordinate.

## Operational note: the source set is measured over raw bytes

`admissionSourceSetId` hashes the working-tree bytes of the eight members, so a
checkout that differs only in line endings is a different source set. On Windows,
`core.autocrlf=true` rewrites LF blobs to CRLF on checkout and this repository carries
no `.gitattributes` to prevent it. A locally printed `source-set` id will therefore not
match the CI-printed one on such a checkout. That is a line-ending difference, not
drift.

To compare against CI, measure canonical LF blobs:

```bash
git cat-file blob "<commit>:<relative path>" > "<lf root>/<relative path>"
python mating_surface/anchor_node/stc_mary_packet_evidence_admission.py source-set \
  --admission-source-root "<lf root>"
```

The admitted profile digest is unaffected, because it is computed over canonically
re-serialized JSON rather than raw file bytes.

## Boundary

Source admission of this object is separate from applying it to any particular
campaign. A passing conformance run qualifies the **source**. Applying it to a real
configured packet is a separate operator transaction, subject to the drive-conformance
custody policy, and it still records zero packet stages.

No real campaign coordinate or evidence body may enter this repository. Every fixture in
the conformance suite is synthetic.
