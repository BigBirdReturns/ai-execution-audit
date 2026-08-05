# Interface Design Description

## 1. Status

This document is shaped by DI-IPSC-81436, Interface Design Description. It is a working interface-control artifact for the rehearsal station and is not a contract data item unless explicitly invoked and tailored.

## 2. Interface ownership

### Browser presentation

Owns work-area navigation, accessible feedback, and presentation of server-supplied scenario cards, evaluations, and evidence. It does not own authority, lease, replay, partition, reconciliation, or C2SIM semantics.

### Loopback HTTP host

Owns same-origin request handling, input bounds, static documentation delivery, session export, and verification endpoints. It binds only to loopback.

### Interactive session conductor

Loads the source-controlled scenario catalog, maps bounded user actions into calls to the canonical authority runtime and transport fault machine, records the action ledger, computes the acceptance evaluation, and assembles public state.

### Canonical authority runtime

Owns authority profile evaluation, partition epoch, offline lease, local-operator requirement, allow/hold/refuse/safe-state dispositions, admission tickets, delivery replay refusal, and reconciliation.

### Standards and transport layer

Owns exact artifact custody, schema-valid semantic receipts, payload digests, deterministic transport faults, journal identity, and detached transport verification.

## 3. Browser-to-host interface

### GET `/api/scenarios`

Returns the bounded public scenario catalog. Definitions, procedures, configurations, and checks originate from `scenarios.mjs`.

### GET `/api/state`

Returns `standards-interactive-rehearsal-state/2`, including scenario identity and server-owned evaluation.

### POST `/api/action`

Input:

```json
{
  "action": "cut_headquarters | isolate | issue_order | issue_report | advance | restore | reconcile | reset",
  "input": {}
}
```

For `reset`, `input` may carry a bounded `scenarioId` and complete configuration object. Other actions accept only their documented bounded inputs.

State-changing requests require loopback Host, same-origin or absent Origin, same-site fetch context, and `application/json` content type.

### GET `/api/verify`

Exports the current action ledger and replays it through the same source identities. Returns pass or refuse.

### GET `/api/export`

Returns the interactive session receipt.

### GET `/docs/<document>.md`

Returns packaged support documentation as UTF-8 Markdown. Path traversal is refused by the static path resolver.

## 4. Scenario and acceptance model

`scenarios.mjs` defines a content-addressed catalog. The session binds one scenario definition, its baseline configuration, ordered procedure, and machine-evaluated checks. The server classifies each state as pass, fail, incomplete, or deviated. Browser JavaScript may render these results but may not define checks or calculate acceptance.

## 5. User-interface state model

The interface presents three independent state dimensions:

1. **Run lifecycle**: Ready, Running, Awaiting review, Complete.
2. **Communications**: Connected, Headquarters denied, Isolated, Restored.
3. **Authority disposition**: Initialized, Allow, Hold, Refuse, Safe state, Explicitly superseded, Continuous authority, Human required, Returning authority absent.

The dimensions must not be collapsed into one color or one generic health label.

## 6. Interaction model

The primary sequence is Plan, Run, Evaluate, Evidence. Guide is available at any time.

Critical or terminal actions require confirmation:

- isolate node;
- classify returning authority;
- reset a started run.

Errors remain visible until superseded by a later action. Each error includes a code, application-level explanation, and recovery instruction.

## 7. Data minimization

The browser receives message identities, decision receipts, transport metrics, and source provenance. It does not receive standard XML payloads, private key material, provider implementation details, or operational target data.

## 8. Replaceable provider boundary

A provider enters at the program-selected standard port. The provider-specific adapter may translate only the residue between its native representation and the authorized standard artifact. The rehearsal UI does not adopt provider product terms or become a provider dashboard.
