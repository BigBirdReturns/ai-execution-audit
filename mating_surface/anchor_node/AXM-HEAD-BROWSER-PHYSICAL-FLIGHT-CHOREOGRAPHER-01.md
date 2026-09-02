# AXM HEAD Browser Physical Flight Choreographer 01

## Classification

This increment is a supplier-neutral, private physical-flight choreographer above the admitted browser probe and Manifest V3 operator console. It converts a content-bound seat card, exact private prompt bytes, exact one-token reference-output bytes, and a separately content-bound postflight supplement into a bounded sequence of admitted probe invocations. It does not implement distributed inference, discover a supplier, contact an endpoint, open a room, select a model, or infer facts that the browser did not observe.

The stable execution interface remains `axm/distributed-model-inference@1`. Supplier and actor identity remain outside the executable profile, card, supplement, extension, work unit, route identity, and public claim surface.

## Predecessor floor

The choreographer is derived above the admitted operation-plan source at commit `e78bb4e8a4115b2191967d1ffcd1d744d77ce050`, tree `83006c13dd14f670785ffb57bd62d44b502d73a8`. It also binds the admitted operator-console implementation at commit `ce93cf8856b7fcc9b172b9251b9665df50fdeda4`, tree `664784d10309665eb3b993ce8f6df4eb5b10baf7`.

The derivative extension copies the admitted browser probe, operator contract, and service worker without modification. Their exact byte counts, Git blob identities, and SHA-256 values are part of the profile. A dependency substitution refuses profile validation and extension construction.

## Corrected execution model

A complete physical observation cannot be compiled honestly as one uninterrupted plan because several required values exist only after the live transaction begins. Output timing, the exact candidate-output digest, the selected candidate-pair class, the controlled-member-removal terminal, recovery state, browser-visible network exposure, and the evidence references that bind those observations cannot be invented before execution.

The choreographer therefore separates the transaction into governed phases while preserving one document session and one private page ledger:

1. Bind the private seat card, prompt bytes, and one-token reference-output bytes.
2. Open one exact document session and require a pristine early-installed probe ledger. At most three discretionary status inspections are permitted so the fixed worker-session reserve remains closed.
3. Require an explicit static-observation acknowledgement and a current availability mark no more than fifteen minutes old, then record the static availability, executable adapter artifact, artifact-bound pipeline formation, member denominator, model manifest, and model artifacts.
4. Stop at an explicit prompt barrier. Record `performance-start` in the target page, erase the locally displayed prompt, then require the operator to submit the exact bound prompt.
5. Accept the exact visible output through a private side-panel field, copy its bytes into the bounded validation operation, erase the field before validation completes, require byte and digest identity with the one-token reference, and record one token mark plus output equivalence.
6. Stop at an explicit controlled-removal barrier. The operator performs the designated removal and recovery procedure outside the panel.
7. Validate a content-bound postflight supplement carrying only the observed drop disposition, browser-bounded privacy declaration, and nine SHA-256 evidence references. Record that denominator and sample peer statistics.
8. Stop at a separate export acknowledgement, export the exact private capture, and close the document session.

The panel never records prompt text, output text, endpoint identity, host identity, SDP, ICE addresses, response bodies, credentials, or private filenames in its event log. The prompt preview is erased immediately after the target-page start mark. The output textarea is erased before its byte-count and digest verdict is acted upon, including the mismatch path.

## One-token exact-output challenge

The physical prompt is selected so that the complete expected answer is one exact UTF-8 token with no surrounding whitespace. The reference-output file is limited to 256 bytes and must be a trimmed single line. The card binds its SHA-256, byte count, token count, and private reference-evidence digest.

The panel accepts the exact visible candidate output only after the measured prompt has completed. It hashes the pasted bytes in memory and refuses any byte-count or digest mismatch before calling `markToken` or `markEquivalence`. The textarea is cleared before the probe calls occur. The panel and probe therefore retain the candidate digest and evidence reference without retaining output text.

This constraint removes the need to predeclare or reconstruct a multi-token timing series from a browser interface that does not expose token callbacks. It qualifies only the exact challenge used during the transaction.

## Card and supplement custody

The flight card contains static, pre-observable facts and references only. It binds:

- transaction and seat SHA-256 references;
- the canonical seat identifier and expected pipeline role;
- exact prompt and one-token output byte identities;
- availability and executable-adapter evidence references;
- artifact-bound formation semantics and capacity/topology receipts;
- the complete member denominator and opaque local aliases;
- model-manifest identity and contiguous layer-artifact assignments;
- the designated drop-target alias;
- the complete request budget; and
- the fixed no-authority claim boundary.

The postflight supplement is created only after the controlled removal has been observed. It binds the card, transaction, seat, output-equivalence evidence, controlled-drop disposition, browser-observer-bounded privacy declaration, and all nine receipt classes in the admitted order. It contains no terminal decision and cannot manufacture `READY_FOR_NAMED_HUMAN` or `OBSERVED_ROUTE_CANDIDATE`.

Both objects use content-derived identities. A changed value, hand-edited identifier, reordered receipt, unresolved member alias, capacity mismatch, layer gap, forbidden field, raw coordinate, or claim-boundary change refuses before the corresponding phase executes.

## Request budget

Every admitted probe invocation is followed by a fresh worker `status` request. The choreographer also reserves four worker-session requests for bounded session operations. For a card with `M` members and `A` model artifacts:

```text
probeInvocationCount = 21 + M + A
sessionRequestCount  = 2 * probeInvocationCount + 4
```

The four-request reserve is allocated to at most three discretionary status inspections and one closing request. The panel refuses a fourth manual inspection without consuming a worker request. The maximum supported denominator is 32 members and 200 artifacts. That produces 253 probe invocations and 510 worker-session requests, which remains below the admitted 512-request ceiling. A card at 201 artifacts or any card whose computed session request count exceeds 512 is refused before a document session opens.

## Failure and restart law

The panel validates the inspection attached to every invocation and then obtains a fresh post-invocation status inspection before accepting the result or advancing phases. An absent `probeRefused` field, non-null refusal, document replacement, channel loss, request timeout, session exhaustion, malformed opaque member result, capture overflow, output mismatch, supplement mismatch, or invocation-denominator drift stops the run.

Before the first mutating call, session loss returns the panel to the loaded-card state. After any mutating call may have begun, failure seals `HALTED_PARTIAL_CAPTURE`, blocks card replacement and session reopening, and instructs the operator to discard the page ledger. A completed lifecycle is also sealed. A fresh run requires a new target document and a reloaded panel.

An open-session inspection failure retains the worker-returned session identifiers long enough to request closure. If closure cannot be confirmed, the owning runtime port is disconnected so the worker deletes the session before a later attempt.

## Seat identity law

Seat routing is determined by the content-bound card and the assignment reference, never by an informal README title or archive display name. `seat-01` must carry expected role `pipeline-input`; `seat-02` must carry expected role `pipeline-output`. A mismatch refuses card validation. The two cards must bind distinct seat references and the same transaction reference before they may be packaged as one physical run.

## Claim boundary

The choreographer is an observation instrument. Building, validating, loading, or executing it does not establish that a supplier endpoint was contacted, a model was downloaded, a peer connection formed, inference executed, a physical audition completed, or a route terminal was produced. Those facts remain false in every profile, card, supplement, build manifest, verifier receipt, and synthetic fixture.

The choreographer does not qualify a supplier or the physical Estate. It does not supply named-human confirmation. Mission and command authority remain `none`. The existing packet compiler and independent verifier remain authoritative for the later body-free route disposition.

## Control question

Can two independently operated seats use the same admitted probe and supplier-neutral interface to record static formation facts, a live exact-output challenge, a controlled member removal, and the complete postflight evidence denominator while making every predeclared value, operator acknowledgement, informal package label, and local panel state incapable of inventing a physical observation or widening authority?
