# STC MARY sealed-campaign compatibility 01

## What this object is

A **source-authenticated compatibility verifier** for one already sealed, already
detached-verified private campaign package.

It is not a conductor. It is not a repaired conductor. It never claims to be the source
that produced the predecessor ledger, and it never rewrites that ledger.

## Why it exists

The admitted packet sealer and the admitted flight conductor disagree on the public
disposition schema.

The conductor requires:

```python
require(
    value.get("campaignLabel") == campaign_label,
    "PUBLIC_DISPOSITION_BINDING_INVALID",
    "public disposition names another campaign",
)
```

The sealer's closed public-disposition schema has a 21-key exact denominator that does
not contain `campaignLabel`, and the physical-flight validator uses exact-key
validation. Adding the field would invalidate the disposition at the sealer boundary.

Therefore **no valid disposition emitted by the admitted sealer can satisfy the
conductor's campaign-label predicate.** The refusal is deterministic source law, not
incomplete sealing. Re-sealing cannot change it.

A complete private campaign can consequently reach:

```text
private_packet:             CLOSED
packet stages:              16 / 16
stage terminals:            15 PASS / 1 HUMAN_REQUIRED / 0 REFUSED
detached verification:      PASS
```

and still be driven to `sealed_flight: REFUSED`.

## What this verifier does instead

It binds the sealed result through identities the admitted chain actually emits:

```text
workstation marker  ->  campaignId, configId, pathMapId, sourceSetId
campaign config     ->  conductorSourceSetId
packet marker       ->  campaignLabel, packetId
packet state        ->  packetId, sealed, sealedDispositionId
sealed marker       ->  runId, dispositionId
sealed manifest     ->  runId, dispositionId, member byte identities
public disposition  ->  runId, dispositionId
detached verification -> runId, dispositionId
```

Every one of those identities is a content identity, so the verifier **recomputes each
one from its own body** rather than trusting the stored value. `runId` and
`dispositionId` must agree across every schema that carries them.

## Source pinning

The verifier separately identifies two source sets and refuses if they overlap:

- **predecessor conductor source set** — measured from an exact predecessor checkout and
  required to equal the `sourceSetId` the frozen campaign recorded at initialization;
- **repair verifier source set** — this object's own members.

It then reads the impossible predicate out of the *measured* predecessor bytes and
requires it to be present. The predecessor's refusal is retained as evidence: the
sealed-flight ledger row must still read `REFUSED` with reason
`PUBLIC_DISPOSITION_BINDING_INVALID`. A campaign whose refusal has been discharged or
rewritten is refused here.

## What it refuses to do

```text
execute the predecessor conductor          -> never
rewrite the predecessor ledger             -> never
reseal or mutate the sealed package        -> never
replay any packet stage                    -> never
read an evidence body into public output   -> never
grant any qualification or authority       -> never
```

Mutation is not merely avoided by convention; it is fenced. The verifier digests the
whole sealed root and the packet state before and after the run and refuses with
`SEALED_PACKAGE_MUTATED` or `PACKET_STAGES_REPLAYED` if either fence moves.

## Terminal

```text
SEALED_CAMPAIGN_COMPATIBLE
```

reached only when all of the following hold:

```text
predecessor conductor source set exact
predecessor refusal retained = PUBLIC_DISPOSITION_BINDING_INVALID
repair verifier source separately identified
packet marker/state binding exact
packet sealed = true
packet sealedDispositionId exact
stage denominator = 16
terminal denominator = 15 PASS / 1 HUMAN_REQUIRED / 0 REFUSED
unresolved obligation retained
sealed marker/manifest/disposition/detached-verification bindings exact
runId equal across every carrying schema
dispositionId equal across every carrying schema
manifested file bytes unchanged
detached verification = PASS
deterministic receipt replay = true
private evidence bodies = 37
public evidence bodies = 0
body-free public disposition = true
private physical flight complete = true
packageMutated = false
packetStagesReplayed = false
all stronger qualifications = false
authority = none
```

The denominators are carried by the admitted profile, not hardcoded in the verifier.

## Bootstrap authentication

Called directly, the verifier reports `bootstrapAuthenticated: false` and is
structurally incapable of setting that flag itself.

The external bootstrap measures the frozen verifier bytes, executes the measured copy in
an isolated interpreter (`-I -S`) from a foreign temporary directory, validates the
direct receipt — including that the verifier bound the *stored* repair source member to
the bytes that actually executed — and only then sets `bootstrapAuthenticated: true`.

## Operator lanes

```powershell
# canonical: measured, isolated, bootstrap-authenticated
.\stc-mary-sealed-campaign-compatibility.ps1 bootstrap-verify `
  --workstation        <frozen workstation root> `
  --conductor-checkout <exact predecessor conductor checkout> `
  --out                <receipt outside every measured surface>

# direct, not bootstrap-authenticated
.\stc-mary-sealed-campaign-compatibility.ps1 verify --workstation ... --conductor-checkout ...

# admission helpers
.\stc-mary-sealed-campaign-compatibility.ps1 profile-digest
.\stc-mary-sealed-campaign-compatibility.ps1 source-set
```

The receipt is body-free and carries no path, host, credential, evidence filename, or
evidence body. It may be written only outside the workstation and outside the repair
source root.

## Operational note: the predecessor checkout must be byte-exact

`PREDECESSOR_SOURCE_SET_DRIFT` compares raw member bytes, so a checkout that differs only
in line endings is a different source set. On Windows, `core.autocrlf=true` rewrites LF
blobs to CRLF on checkout, and this repository carries no `.gitattributes` to prevent it.

Supply a predecessor checkout materialized the same way the frozen campaign's checkout
was, or materialize it from exact Git blobs:

```bash
git cat-file blob "<commit>:<relative path>" > "<relative path>"
```

This is a real constraint, not a defect in the verifier: the whole point of the check is
that the predecessor source is exact. The admitted profile digest is unaffected, because
it is computed over canonically re-serialized JSON rather than raw file bytes.

## Boundary

Source admission of this object is separate from applying it to any particular campaign.
A passing conformance run qualifies the **source**. Applying it to a real sealed package
is a separate operator transaction, subject to the drive-conformance custody policy.

This object closes nothing for future campaigns. The conductor's own binding repair is a
separate transaction against a separate issue and branch, so that the future source
repair can never become the evidence that authenticates a frozen predecessor.
