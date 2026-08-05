# Human-System UI and Documentation Expectations

## Purpose

This note translates the public defense human-systems, human-engineering, accessibility, C2SIM, and software-documentation baseline into an explicit interaction model for the rehearsal station. It describes what the people evaluating or operating this object should expect to see and do. It does not claim formal MIL-STD-1472, Section 508, operational, or target-hardware qualification.

## Object classification

The station is an acceptance and rehearsal instrument. It is not a tactical common operating picture, a mission-command product, a vendor interface, or an operational authority source.

Its primary job is to make a bounded claim testable:

```text
planned condition
  -> operator or test-conductor action
  -> server-owned authority decision
  -> transport and receiver outcome
  -> expected-versus-observed assessment
  -> detached replay and retained evidence
```

## Expected roles

### Test conductor

The conductor selects a qualified scenario, makes the expected result explicit, confirms preconditions, executes the procedure, preserves deviations, and exports the receipt.

### Operator or mission subject-matter expert

The operator assesses whether the action, state, reason, and recovery are understandable without reading source code or raw JSON.

### Evaluator

The evaluator compares expected and observed behavior, determines whether the test is complete, and runs detached replay before accepting the result.

### V&V reviewer

The reviewer checks source custody, standard-artifact custody, semantic-message identity, transport history, authority receipts, final state, and replay closure.

### Integrator

The integrator uses the interface and traceability artifacts to replace the public reference fixture with a program-selected standard port without changing the station's authority or evidence roles.

## Expected interaction workflow

### Plan

The interface should present the scenario objective, expected result, pass condition, procedure, and initial conditions before execution. Setup should be visibly separate from operation.

### Run

The interface should show the next expected action, enabled server-authorized actions, and three separate state dimensions:

1. run lifecycle;
2. communications condition;
3. authority disposition.

A connected link must not imply that a message was authorized. An authorized message must not imply that transport accepted it only once.

### Evaluate

The interface should compare the selected scenario card with observed behavior and distinguish pass, fail, and incomplete. This comparison supports the evaluator but does not replace detached verification.

### Evidence

The interface should present plain-language findings first, then exact IDs, source hashes, event history, and the machine receipt. Evidence should be exportable without exposing the standard XML payloads in browser state.

### Guide

The interface should route each role to task-specific documentation rather than forcing every user through one large manual.

## Expected feedback and error behavior

- Every action receives perceptible feedback.
- A delayed request receives visible processing status.
- Repeated activation is blocked while the request is active.
- Refusals remain visible with an application-level code, plain-language explanation, and recovery instruction.
- Dangerous, terminal, or history-changing actions require confirmation.
- Color reinforces status but never carries it alone.
- Raw identifiers remain available but do not replace human-readable state and reason text.

## Expected documentation set

The support package should include:

- an operator quickstart;
- a task-oriented user guide;
- a test-conductor guide;
- a verifier guide;
- an interface design description;
- a software test plan;
- a software test report;
- an accessibility and human-factors plan;
- a traceability matrix;
- a software version description;
- a public reference baseline and claim boundary.

The documents are DID-shaped working artifacts. They become contractual data items only when an acquisition instrument invokes and tailors them.

## Acceptance behavior

A usable station lets a representative user identify the current communications and authority state, find the next correct action, understand a hold, refusal, safe-state transition, replay refusal, or human-required return, recover from an error, and preserve evidence without inspecting the raw JSON.

The station is not human-system qualified until representative users, tasks, environment, workload, equipment, accessibility requirements, and target hardware have been evaluated under a program-approved plan.
