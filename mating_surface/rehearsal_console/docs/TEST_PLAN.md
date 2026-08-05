# Software Test Plan

## 1. Purpose

This plan describes qualification of the denied-communications authority rehearsal station. It is shaped by DI-IPSC-81438, Software Test Plan, and is not a contract data item unless explicitly invoked and tailored.

## 2. Test objects

- exact public C2SIM reference artifact and XSD 1.1 catalog;
- four schema-valid semantic messages;
- payload-opaque transport fault machine;
- canonical `MessageAuthorityRuntime`;
- source-controlled scenario catalog and server-owned acceptance evaluator;
- interactive session conductor;
- separate local evaluator-disposition signer and verifier;
- digest-only external-evidence admission and verifier;
- loopback HTTP host;
- browser presentation and support documentation;
- export and detached replay receipt chain.

## 3. Test environment

- GitHub Actions Ubuntu runner;
- Node.js 24;
- Python 3.12;
- `xmllint --noout --nonet`;
- hash-pinned `xmlschema` and `elementpath` packages;
- headless Google Chrome desktop and mobile viewports;
- no external runtime network dependency after source checkout.

## 4. Qualification cases

1. Baseline partition, duplicate order, delayed report, explicit supersession.
2. Local operator absent.
3. Offline lease expiry.
4. Total isolation.
5. Conflicting returning authority.
6. Returning authority absent.
7. Exact catalog and scenario-definition identity.
8. Qualified pass, expectation fail, incomplete, and deviation semantics.
9. Exported session replay.
10. Live configuration deviation before message lock.
11. Session closure refusal.
12. Evaluator accept, reject, and defer disposition.
13. Automatic non-pass cannot receive local accept.
14. Evaluator signature, session-binding, and immutable-registry refusal.
15. Host, Origin, fetch-site, content-type, request-size, and path-boundary refusal.
16. Keyboard tab navigation and visible focus.
17. Persistent action feedback and recovery guidance.
18. Critical-action confirmation.
19. Color-independent state presentation.
20. Documentation inventory and link integrity.
21. Desktop and mobile responsive rendering.
22. Digest-only private external source retains no raw bytes, filename, local path, body, or encoded payload.
23. External source artifact and observation identities reconstruct exactly.
24. Required external claims cannot pass without cited observations.
25. External automatic status cannot be caller-promoted.
26. Even when every required external claim is marked pass, admission remains incomplete and acceptance-ineligible.
27. Self-asserted catalog, definition, session receipt, session verification, or passing detached-replay values are refused before evaluation.
28. Another source evidence set cannot borrow or rewrite a canonical session closure.
29. Producer-report assertions remain claim dispositions rather than independent observations.

## 5. Methods

- source-level conformance tests;
- exact digest and byte-count checks;
- semantic schema validation;
- deterministic positive and negative runtime cases;
- detached receipt replay;
- external-evidence receipt reconstruction;
- browser API exercise;
- DOM assertions;
- screenshot inspection;
- accessibility-oriented keyboard and semantic checks;
- documentation traceability audit.

## 6. Acceptance gates

A build is promotable only when:

- all source and runtime tests pass;
- the scenario catalog and every definition reconstruct their content identities;
- every qualified scenario reproduces its expected evaluation and receipt identities;
- changed configuration or off-procedure actions are classified as deviations and cannot pass;
- an automatic non-pass cannot be converted into a local evaluator accept;
- no C2SIM XML payload enters browser state;
- no browser authority or acceptance implementation exists;
- critical actions require confirmation;
- errors are persistent and corrective;
- state is not conveyed by color alone;
- support documentation is packaged and reachable;
- exported sessions replay to the same final identity;
- every retained external-evidence receipt reconstructs exactly;
- private digest-only evidence retains `rawSourceCommitted: false` and no raw source path or payload;
- external automatic status is derived from required claims and can only be `fail` or `incomplete`;
- external admission has no automatic-pass or acceptance authority;
- self-asserted canonical catalog, definition, session, verification, and replay values are refused;
- the retained standing-orders external receipt remains `incomplete` and `acceptanceEligible: false`;
- the claim boundary remains visible.

## 7. Deferred tests

- a separately reviewed canonical-closure verifier that loads actual scenario and session artifacts, calls `verifySessionReceipt`, and proves session-side binding to the exact external source evidence set;
- canonical reproduction of the retained external standing-orders source session;
- signed authority or offline-lease object with exact issuer, scope, generation, validity, signature, and verification;
- independent headquarters-link and local-link topology observations;
- receiver-side replay and reconciliation closure for the retained external source;
- formal Section 508 Trusted Tester evaluation;
- formal MIL-STD-1472 human engineering evaluation;
- representative operator usability test;
- workload and time-to-correct-action measurement;
- target MAME and MotionDeck installation;
- touchscreen or gloved-use physical target evaluation;
- operational standard artifact and field-network testing;
- external provider integration.
