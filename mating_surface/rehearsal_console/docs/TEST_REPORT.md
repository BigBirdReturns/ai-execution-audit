# Software Test Report

## 1. Purpose

This report records the current qualification baseline. It is shaped by DI-IPSC-81440, Software Test Report, and is not a contract data item unless explicitly invoked and tailored.

## 2. Baseline under test

The controlling source is the most recent production commit recorded in the packaged build manifest. The station directly imports the canonical authority runtime server-side and uses the retained public C2SIM rehearsal evidence.

## 3. Completed evidence

The prior baseline established:

- exact OpenC2SIM artifact commit and Git blob custody;
- XML well-formedness with network disabled;
- strict local-only XSD 1.1 structural compilation;
- four schema-valid C2SIM messages;
- baseline partition, duplicate, delay, replay, and explicit supersession;
- local-operator hold;
- offline-lease safe state;
- isolated-order refusal;
- conflicting-return human review;
- absent returning authority;
- loopback request-boundary refusals;
- source-pinned pack manifest;
- desktop and mobile browser rendering;
- exported session replay through the same canonical runtime.

## 4. HSI and documentation increment

The current increment adds:

- Plan, Run, Evaluate, Evidence, and Guide work areas;
- explicit separation of run, communications, and authority state;
- qualified scenario cards with objective, expected result, pass condition, and procedure;
- next-action runbook guidance;
- persistent action result, reason, and recovery;
- confirmation for isolation, returning-authority classification, and resetting a started run;
- expected-versus-observed matrix;
- persistent verification and export results;
- role-based support documentation;
- keyboard-operable work-area tabs;
- color-independent text and symbol cues;
- mobile single-column operation.

## 5. Interpretation

Passing automated checks establishes source and interaction-contract consistency. It does not establish that representative warfighters can use the station effectively under operational workload. Human-performance validation remains required before operational use claims.

## 6. Open findings

- No formal Section 508 conformance report exists yet.
- No formal MIL-STD-1472 compliance assessment exists yet.
- No representative operator cohort has completed timed scenarios.
- No physical target, gloved input, low-light, vibration, or degraded-display test has been run.
- No operational C2SIM profile or controlled tactical standard artifact has entered the harness.
- No Polybolos or other provider implementation has entered the standards port.
