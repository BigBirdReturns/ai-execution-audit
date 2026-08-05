# Software Version Description

## 1. Status

This document is shaped by DI-IPSC-81442, Software Version Description. It is a configuration-identification aid and is not a contract data item unless explicitly invoked and tailored.

## 2. Product identity

Product: Denied Communications Authority Rehearsal

Pack version: `1.4.1`

Runtime mode: server-side direct import

Authority implementation: `MessageAuthorityRuntime`

Host: loopback-only Node.js service

Browser: presentation and bounded API requests only

External evidence: digest-only admission and detached integrity verification; no canonical-closure authority

## 3. Version identity

The controlling source commit, build ID, source-file SHA-256 values, scenario catalog ID, semantic conversation ID, verification ID, evaluator-disposition mode, external-evidence qualification ID, external source-evidence-set ID, external automatic status, and external acceptance eligibility are recorded in `build-manifest.json`. The manifest excludes itself from its file list and is content-addressed from the remaining manifest body.

The retained external evidence identities are:

```text
source evidence set
standardsexternalevidenceset1_c7765ccc60f1c8d6b8da1bee1055689eb9a0eea08f786c4b4b5f12bcd759d9c8

qualification receipt
standardsexternalevidencequalification1_bbe95527b8b989b84ffaf24c09909aa4ff066dd942ccac25e8f52e1122284580

verification receipt
standardsexternalevidenceverification1_4ee8c0c0b07904dc23bf7bda2b5c29b486be2f93f2deb956bd8b18f393b5a043
```

## 4. Required environment

- Node.js 24 or newer;
- a modern browser supporting ES modules, Fetch, native Dialog, and accessible form controls;
- no external service after the local pack is built;
- port 8787 available on loopback, unless another permitted loopback port is selected at launch.

## 5. Packaged components

- browser HTML, CSS, and JavaScript;
- loopback HTTP host;
- content-addressed scenario catalog and server-owned acceptance evaluator;
- interactive session conductor;
- canonical authority sidecar;
- semantic conversation verifier;
- transport fault machine and verifier;
- separate local evaluator-disposition module and workspace;
- digest-only external-evidence admission module;
- retained external-evidence qualification and verification receipt;
- exact canonical rehearsal evidence;
- launchers for Windows and POSIX environments;
- role-based support documentation;
- build manifest and package metadata.

The private external log and producer-report bytes are not packaged. The pack retains only their byte counts, SHA-256 identities, bounded observations, and claim dispositions.

## 6. Security and boundary controls

- loopback-only bind;
- Host header allowlist;
- same-origin request enforcement;
- cross-site fetch refusal;
- JSON-only state-changing requests;
- bounded request size;
- strict Content Security Policy;
- static path normalization;
- no remote URLs in the public interface;
- no C2SIM XML in browser state;
- no scenario or acceptance implementation in browser code;
- catalog, definition, evaluation, and state identities in exported receipts;
- automatic non-pass cannot receive a local evaluator accept;
- private digest-only external evidence cannot retain raw bytes, a source path, filename, body, or encoded payload;
- external automatic result is derived and cannot be caller-promoted;
- external admission can produce only `fail` or `incomplete`, never acceptance eligibility;
- self-asserted catalog, definition, session, verification, and replay closure values are refused;
- another external source cannot borrow or rewrite a closure;
- any future external pass requires a separate verifier that loads the actual artifacts, calls `verifySessionReceipt`, and proves session-side binding to the exact source evidence set.

## 7. Known limitations

- retained external standing-orders result is `incomplete` and `acceptanceEligible: false`;
- reference artifact is public rehearsal material, not an operational controlled artifact;
- no canonical-closure verifier is implemented for external evidence;
- no canonical session reproduces the retained external source evidence set;
- no signed authority, duplicate replay, returning supersession, receiver-ledger closure, or detached replay is retained for that external source;
- no representative operator usability result;
- no formal Section 508 conformance report;
- no formal MIL-STD-1472 evaluation;
- no target MAME or MotionDeck physical installation;
- no field network or operational message profile;
- no external provider implementation;
- no command, targeting, engagement, effector, execution, or weapons authority.
