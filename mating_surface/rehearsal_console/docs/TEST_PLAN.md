# Software Test Plan

## 1. Purpose

This plan describes qualification of the denied-communications authority rehearsal station. It is shaped by DI-IPSC-81438, Software Test Plan, and is not a contract data item unless explicitly invoked and tailored.

## 2. Test objects

- exact public C2SIM reference artifact and XSD 1.1 catalog;
- four schema-valid semantic messages;
- payload-opaque transport fault machine;
- canonical `MessageAuthorityRuntime`;
- interactive session conductor;
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
7. Exported session replay.
8. Live configuration replay before message lock.
9. Session closure refusal.
10. Host, Origin, fetch-site, content-type, request-size, and path-boundary refusal.
11. Keyboard tab navigation and visible focus.
12. Persistent action feedback and recovery guidance.
13. Critical-action confirmation.
14. Color-independent state presentation.
15. Documentation inventory and link integrity.
16. Desktop and mobile responsive rendering.

## 5. Methods

- source-level conformance tests;
- exact digest and byte-count checks;
- semantic schema validation;
- deterministic positive and negative runtime cases;
- detached receipt replay;
- browser API exercise;
- DOM assertions;
- screenshot inspection;
- accessibility-oriented keyboard and semantic checks;
- documentation traceability audit.

## 6. Acceptance gates

A build is promotable only when:

- all source and runtime tests pass;
- all seven qualified scenarios reproduce expected identities;
- no C2SIM XML payload enters browser state;
- no browser authority implementation exists;
- critical actions require confirmation;
- errors are persistent and corrective;
- state is not conveyed by color alone;
- support documentation is packaged and reachable;
- exported sessions replay to the same final identity;
- the claim boundary remains visible.

## 7. Deferred tests

- formal Section 508 Trusted Tester evaluation;
- formal MIL-STD-1472 human engineering evaluation;
- representative operator usability test;
- workload and time-to-correct-action measurement;
- target MAME and MotionDeck installation;
- touchscreen or gloved-use physical target evaluation;
- operational standard artifact and field-network testing;
- external provider integration.
