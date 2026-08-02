# Software User Guide

## 1. Scope

This guide describes hands-on use of the denied-communications authority rehearsal station. It follows the intent of DI-IPSC-81443, Software User Manual, by organizing instructions around user positions and tasks. It is not a contract data item unless explicitly invoked and tailored.

## 2. User positions

### Test conductor

Plans the run, confirms preconditions, executes the qualified procedure, records deviations, and preserves evidence.

### Operator or mission subject-matter expert

Assesses whether the interface supports rapid, correct understanding under realistic workload. The SME does not need to inspect source hashes unless also serving as an evaluator.

### Evaluator

Compares expected and observed behavior, verifies the exported session, and records pass, fail, or incomplete status.

### V&V reviewer

Inspects exact message, artifact, runtime, transport, authority, and session identities.

## 3. Work areas

### Plan

Plan separates test setup from execution. Select a qualified scenario, read its objective and pass condition, review the conditions, and start a clean run. Starting a new plan replaces the current local session after confirmation.

### Run

Run presents the current procedure, the next expected action, three separate state planes, the latest authority receipt, message and transport metrics, persistent feedback, and the enabled action set.

### Evaluate

Evaluate compares the scenario card with the observed state. The comparison is a test-conductor aid. Detached session replay is the controlling verification mechanism.

### Evidence

Evidence exposes source provenance, event history, the current state object, and export. Human-readable findings are presented before exact identifiers.

### Guide

Guide provides role guidance, workflow explanation, a decision glossary, and links to the full documentation set.

## 4. Qualified scenarios

### Baseline partition and explicit return

Expected: four unique messages accepted, one duplicate order refused as replay, and returning authority explicitly supersedes the local generation.

### Local operator absent

Expected: the order is held with `LOCAL_OPERATOR_REQUIRED` and does not enter transport.

### Offline authority lease expiry

Expected: the order produces `safe_state` with `OFFLINE_LEASE_EXPIRED` after the clock advances beyond the delegated lease.

### Total node isolation

Expected: the order is refused with `MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE`.

### Conflicting returning authority

Expected: final state `human_required` with both histories preserved.

### Returning authority absent

Expected: final state `returning_authority_absent`; no reconciliation receipt is invented.

## 5. Error handling

The station uses persistent feedback. A refused request displays an error code, an application-level explanation, and a recovery action. Common recovery paths are:

- `CONFIG_LOCKED`: reset, change the plan, and start a new run;
- `RECONCILIATION_REQUIRED`: restore communications if needed, then classify returning authority;
- `SESSION_CLOSED`: export evidence if needed, then reset;
- `MESSAGE_ALREADY_SENT`: reset to rerun the message;
- `HOST_FAILURE`: confirm the loopback host is still running and reload.

## 6. Keyboard and accessibility

- Use Tab and Shift+Tab to move among controls.
- Use Left and Right Arrow, Home, and End to move among work-area tabs.
- Native form controls retain platform keyboard behavior.
- State is conveyed by text, symbols, border treatment, and color together.
- Critical dialogs place focus inside the dialog and return focus after dismissal.

Formal Section 508 conformance testing remains a separate acceptance activity.
