# Evaluator Disposition and Acceptance-Package Guide

## Purpose

The rehearsal station produces an automatic scenario evaluation and a detached replay verification. Those objects are engineering evidence. They are not a human or organizational acceptance decision.

The evaluator-disposition lane preserves that distinction by issuing a separate receipt that references the exact session, scenario definition, automatic evaluation, final state, and detached verification. The evaluator may accept, reject, or defer. The automatic evidence is never rewritten to match the human disposition.

## Roles

The evaluator is a named local user reviewing a completed or partial rehearsal. The evaluator identifier, role, organization, disposition, rationale, and issue time are retained in the receipt.

The local rehearsal host signs the disposition with an ephemeral Ed25519 process key. That signature protects receipt integrity inside the running host. It does not prove the evaluator's real-world identity, clearance, delegation, or organizational acceptance authority.

## Preconditions

Every disposition requires:

1. an exported `standards-interactive-rehearsal-receipt/2`;
2. a passing `standards-interactive-rehearsal-verification/2` covering that exact receipt;
3. closure to the same scenario catalog, scenario definition, automatic evaluation, and final state;
4. a bounded evaluator identifier and role.

An `accept` disposition additionally requires the automatic evaluation to be `pass`. A local evaluator cannot convert `fail`, `incomplete`, or `deviated` into an accepted qualified result.

`reject` and `defer` require a rationale. An acceptance rationale is optional but recommended when the review basis is not obvious from the retained evidence.

## Operation

Open `/evaluator.html` from the local rehearsal host after executing or reviewing a session.

1. Review the selected scenario, automatic evaluation, detached replay status, and session receipt identity.
2. Enter the evaluator identifier, role, and organization.
3. Select `accept`, `reject`, or `defer`.
4. Enter the rationale where required.
5. Issue the disposition.
6. Verify the disposition signature and session closure.
7. Export the combined acceptance package.

One immutable disposition may be issued per session receipt. Resetting or changing the rehearsal creates another session receipt and therefore another disposition target. The registry does not overwrite a prior receipt.

## Receipt chain

```text
source-controlled scenario definition
        ↓
automatic scenario evaluation
        ↓
interactive session receipt
        ↓
detached session verification
        ↓
local evaluator disposition
        ↓
detached disposition verification
        ↓
combined acceptance package
```

The combined package preserves all four controlling objects:

- the original session receipt;
- the detached session verification;
- the separate evaluator disposition;
- the detached disposition verification.

## Disposition meanings

### Accept

The evaluator agrees that the replay-verified automatic pass supports the stated rehearsal acceptance claim. The local receipt does not make the evaluator an authorized program acceptance official.

### Reject

The evaluator does not accept the run as evidence for the stated purpose. The rationale records why. The automatic evaluation remains unchanged and available for comparison.

### Defer

The evaluator postpones a decision pending additional evidence, representative-user review, target-system testing, security review, or another named dependency. The rationale must identify the missing basis.

## API boundary

The loopback host provides:

```text
GET  /api/disposition
POST /api/disposition
GET  /api/disposition/verify
GET  /api/acceptance-package
```

The browser submits evaluator input and renders receipts. Signature generation, acceptance precondition checks, immutable registry behavior, detached verification, and package identity execute server-side.

## Integration target

A program deployment should replace the ephemeral local signer with an approved identity and authorization mechanism. Candidate mechanisms include a program PKI credential, device-backed signing key, authenticated evaluator session, or an external workflow that signs the exported package. That replacement must preserve the separation between automatic evidence and human disposition.

## Claim boundary

This lane qualifies local receipt integrity, session closure, and the rule that an automatic non-pass cannot be locally accepted. It does not authenticate the evaluator against a personnel system, establish legal or contractual acceptance, satisfy records-management policy, or qualify operational command, targeting, engagement, effector, execution, or weapons authority.
