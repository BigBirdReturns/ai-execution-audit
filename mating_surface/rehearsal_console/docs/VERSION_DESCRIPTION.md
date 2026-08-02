# Software Version Description

## 1. Status

This document is shaped by DI-IPSC-81442, Software Version Description. It is a configuration-identification aid and is not a contract data item unless explicitly invoked and tailored.

## 2. Product identity

Product: Denied Communications Authority Rehearsal

Runtime mode: server-side direct import

Authority implementation: `MessageAuthorityRuntime`

Host: loopback-only Node.js service

Browser: presentation and bounded API requests only

## 3. Version identity

The controlling source commit, build ID, source-file SHA-256 values, scenario catalog ID, semantic conversation ID, and verification ID are recorded in `build-manifest.json`. The manifest excludes itself from its file list and is content-addressed from the remaining manifest body.

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
- exact rehearsal evidence;
- launchers for Windows and POSIX environments;
- role-based support documentation;
- build manifest and package metadata.

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
- catalog, definition, evaluation, and state identities in exported receipts.

## 7. Known limitations

- reference artifact is public rehearsal material, not an operational controlled artifact;
- no representative operator usability result;
- no formal Section 508 conformance report;
- no formal MIL-STD-1472 evaluation;
- no target MAME or MotionDeck physical installation;
- no field network or operational message profile;
- no external provider implementation;
- no command, targeting, engagement, effector, execution, or weapons authority.
