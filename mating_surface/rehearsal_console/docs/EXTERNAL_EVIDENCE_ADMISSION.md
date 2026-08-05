# External Evidence Admission and Qualification

## Purpose

This guide defines how the rehearsal station admits a log, report, screenshot, export, or other artifact that was produced outside the canonical interactive session runtime.

External evidence may qualify a bounded observation. It does not become a source-controlled scenario result merely because its subject resembles a qualified case. Automatic evaluation, detached replay, evaluator disposition, and program acceptance remain separate objects.

## Operating classification

The external-evidence lane belongs in **Evidence**. It does not create another tactical screen and it does not alter Plan, Run, or Evaluate for a canonical session.

The principal users are:

- the test conductor, who identifies the source event and its declared procedure;
- the evaluator, who separates observed facts from producer interpretation;
- the V&V reviewer, who reconstructs hashes, observations, claim dispositions, and closure identity;
- the integrator, who determines whether a later canonical scenario can reproduce the source evidence set.

## Admission transaction

```text
private or public source artifact
→ exact byte count and SHA-256 identity
→ bounded observations
→ claim-by-claim disposition
→ producer-report correction
→ self-asserted canonical closure refused
→ bounded fail or incomplete result
→ detached receipt-integrity verification
```

A private source is admitted as `private_digest_only`. The repository may retain its byte count, SHA-256 identity, bounded observations, and claim dispositions. It must not retain the raw source bytes, filename, local path, body, or encoded payload.

A producer report remains a report under review. It does not independently prove its own operator-presence, topology, authority, replay, reconciliation, or readiness claims.

## Automatic result law

The verifier derives the automatic result. Callers cannot submit or overwrite it.

```text
required claim fails
→ fail and not acceptance-eligible

otherwise
→ incomplete and not acceptance-eligible
```

`pass_within_harness`, `pass_for_logged_sample`, `partial`, `not_run`, `not_witnessed`, and `not_acquired` are evidence-bearing states. None is treated as a complete required-claim pass.

This admission module deliberately has no automatic `pass` path. Its `canonicalClosure` object may retain the exact external `sourceEvidenceSetId` as self-custody, but catalog, definition, session receipt, session verification, and detached-replay claims must remain absent. Self-asserted values fail closed.

A future canonical-closure transaction requires a separately reviewed verifier that loads the cited scenario catalog and definition, loads the actual session receipt and verification, calls the canonical `verifySessionReceipt` implementation, and proves that the verified session itself binds the exact external source evidence set. That authority is not implemented by external-evidence admission.

## Retained standing-orders qualification

The retained digest-only receipt is:

```text
mating_surface/rehearsal_console/evidence/external/
  standing-orders-admin-inject-20260802.json
```

Its controlling identities are:

```text
source evidence set:
standardsexternalevidenceset1_c7765ccc60f1c8d6b8da1bee1055689eb9a0eea08f786c4b4b5f12bcd759d9c8

qualification receipt:
standardsexternalevidencequalification1_bbe95527b8b989b84ffaf24c09909aa4ff066dd942ccac25e8f52e1122284580

verification receipt:
standardsexternalevidenceverification1_4ee8c0c0b07904dc23bf7bda2b5c29b486be2f93f2deb956bd8b18f393b5a043
```

The private source bytes are not committed. Their retained identities are:

```text
controlling event log
bytes:   5,122
sha256:  fd408eac2c7743e7cc17058242a5b5ecbc8baaf6441c7af826aa7db2512bb575

producer report under review
bytes:   17,758
sha256:  2217491042db3001b21c60dce55e9d82156ffe862b9e34768004e46f7e81685a
```

## Observed result

The controlling event log identifies an admin TEST ONLY injection path and expressly excludes Lattice auto-detection. The injected DOWN-to-UP interval was 25,505 ms.

```text
threats presented:                   15
decisions retained:                  15
allowlisted SMALL_UAS → AUTHORIZE:   10 / 10
out-of-list MEDIUM_UAS → SAFE_DENY:   5 / 5
presented mapping deviations:         0
feed-to-decision log interval:        1–29 ms
nearest-rank p95:                     29 ms
```

Those intervals are timestamps inside the scripted browser/inject harness. They are not end-to-end network, Lattice, engagement, effector, or weapon-effect latency.

The log also retains a reconciliation acknowledgement with `last_ack=15` and raw `so_period_cleared=0`. No completion meaning is inferred without a field contract and receiver-side closure evidence.

## Automatic disposition

```text
local allowlist decision behavior       pass
admin-injected communications change    pass within harness
signed bounded authority                incomplete
duplicate or replay refusal             not run
returning-authority supersession        incomplete
reconciliation completion               incomplete
operator and separate link witnesses    not witnessed
end-to-end authority transaction        incomplete
operational or human-factors result      not acquired

required claims:                        8
required full passes:                   1
required incomplete states:             7
canonical closure complete:             false
automatic result:                        incomplete
acceptance eligible:                     false
```

Controlling statement:

> Synthetic local allowlist decision behavior passed. End-to-end denied-communications authority acceptance remains incomplete.

## Producer-report corrections

The report correctly describes the admin injection, the 10 allowlisted authorizations, the 5 safe denials, and the observed mapping for the presented cases. It outruns the controlling log when it treats an active-state Boolean as an authority signature, treats the injected interval as a signed lease, asserts independent HQ/local-link and operator-presence witnesses, imports an unwitnessed epoch identifier, asserts replay or explicit returning-authority supersession, interprets acknowledgement as full reconciliation, or concludes that operational capability is ready.

The defensible boundary is:

- no widening was observed across the two tested classes and fifteen presented cases;
- no general authority-width proof was produced;
- no physical network partition or Lattice auto-detection was tested;
- no signed lease, authority generation, issuer, expiry, signature, or validation receipt was retained;
- no duplicate message or receiver replay result was retained;
- no returning generation or explicit supersession receipt was retained;
- no operator-presence or separate local-link witness was retained;
- no detached replay over this external session was retained.

## Verification

From the repository root:

```bash
node --test mating_surface/rehearsal_console/conformance/external_evidence.test.mjs
```

The test suite verifies that:

- the retained receipt reconstructs exactly;
- the private source bytes remain uncommitted;
- digest tampering fails closed;
- a caller cannot promote the automatic result;
- a required pass cannot omit evidence;
- all required claim passes still remain incomplete because admission has no canonical-closure authority;
- self-asserted catalog, definition, session, verification, and replay values are refused;
- another evidence set cannot borrow or rewrite a session closure;
- undeclared receipt fields are refused.

## Next canonical receipt

The next controlled case should freeze the objective, expected result, pass condition, initial conditions, and procedure before action, then retain:

1. one exact session identity across UI, event log, authority object, transport, receiver ledger, replay, and report;
2. a signed authority or lease object with issuer, subject, scope, generation, validity, signature, and verification outcome;
3. independent headquarters-link and local-link observations;
4. out-of-scope, malformed, stale-generation, expired-authority, and bypass refusals;
5. a duplicate delivery with a stable message identity and receiver-side replay refusal;
6. a returning authority generation and explicit supersession, hold, refuse, or human-required classification;
7. receiver accepted, rejected, and duplicate sets;
8. deterministic detached replay over the exact source session;
9. a separately reviewed canonical-closure verifier that loads those artifacts, calls `verifySessionReceipt`, and requires the verified session to bind this exact `sourceEvidenceSetId`.

Representative-user, accessibility, target-hardware, field-network, operational-profile, safety, and provider-integration evaluations remain separate future gates.

## Claim boundary

This lane qualifies digest custody, bounded observations, claim dispositions, and deterministic receipt integrity. It has no automatic-pass or canonical-closure authority. It does not publish private source material, turn a producer report into independent evidence, import another session by analogy, authenticate an evaluator, establish contractual or program acceptance, or grant operational command, targeting, engagement, effector, execution, or weapons authority.
