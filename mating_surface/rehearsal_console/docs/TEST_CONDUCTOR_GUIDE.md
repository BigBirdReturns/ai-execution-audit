# Test Conductor Guide

## 1. Objective

Use the station to convert a denied-communications authority claim into a bounded, repeatable test transaction. The conductor must make the expected outcome explicit before issuing an action and must preserve deviations rather than steering the run toward a preferred result.

## 2. Preflight

Confirm the following before each run:

- the host is bound to loopback;
- the authority implementation is `MessageAuthorityRuntime` and its digest is visible;
- the semantic conversation contains four schema-valid messages;
- the public reference artifact and structural catalog are admitted for rehearsal only;
- the selected source-controlled scenario ID and definition ID match the intended test objective;
- the initial conditions are correct;
- the operator or evaluator understands the stop conditions.

## 3. Conduct rules

1. Start from **Plan** with a clean reset.
2. Read the expected result aloud or record it in the test log.
3. Execute the displayed source-controlled procedure without adding unplanned actions. Any different configuration or action sequence is automatically retained as a deviation and cannot pass acceptance.
4. Confirm isolation and returning-authority classification only after verifying the intended condition.
5. Read persistent feedback after each action.
6. When the observed result diverges, stop and preserve the current state. Do not reset before export.
7. Run detached verification before accepting the run.
8. Export the session receipt and record the receipt ID.

## 4. Qualified procedure cards

### Baseline

1. Cut headquarters link.
2. Issue order.
3. Issue report.
4. Restore communications.
5. Classify returning authority.

Expected: four unique accepts, one replay refusal, explicit supersession, zero pending transport.

### Operator absent

1. Cut headquarters link.
2. Issue order.

Expected: hold with `LOCAL_OPERATOR_REQUIRED`; two initialization messages remain the only accepted messages.

### Lease expiry

1. Cut headquarters link.
2. Advance three ticks.
3. Issue order.

Expected: safe state with `OFFLINE_LEASE_EXPIRED`.

### Isolation

1. Isolate node.
2. Issue order.

Expected: refusal with `MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE`.

### Conflicting return

1. Cut headquarters link.
2. Issue order.
3. Issue report.
4. Restore communications.
5. Classify returning authority.

Expected: `human_required`.

### No returning authority

Use the conflicting-return procedure with Returning Authority set to Absent.

Expected: `returning_authority_absent`; no reconciliation receipt.

## 5. Acceptance interpretation

The server, rather than the browser or conductor, evaluates the session against the selected catalog definition. A run can be `pass`, `fail`, `incomplete`, or `deviated`. Only `pass` is acceptance-eligible, and detached replay must also pass. Do not describe an exploratory variation as a qualified scenario result.

## 6. Deviation record

Record at minimum:

- date and station version;
- source commit and authority-module digest;
- scenario and initial configuration;
- operator role and environment;
- expected outcome;
- first unexpected event or display;
- exact state ID and event reason code;
- whether detached verification passed;
- exported receipt ID;
- disposition: rerun, defect, requirement question, or accepted deviation.

## 7. Human-performance observations

Capture whether the user:

- identified the next expected action without coaching;
- distinguished communications state from authority state;
- understood hold, refuse, and safe state;
- found the recovery instruction without searching the raw JSON;
- recognized that replay refusal occurred after one valid acceptance;
- understood why conflicting return required a human decision;
- completed the scenario without an unintended action.
