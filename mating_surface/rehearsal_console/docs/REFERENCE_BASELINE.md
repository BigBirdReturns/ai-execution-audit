# Human-System and Documentation Reference Baseline

## 1. Purpose

This baseline records the public authorities used to shape the rehearsal station's human-system workflow and documentation. It does not substitute for a program's contract, tailored specification, approved operational concept, or user-representative evaluation.

## 2. Precedence

When requirements conflict, apply them in this order:

1. Contract, statement of work, data-item list, and program-approved tailoring.
2. Program operational concept, target-user tasks, security boundary, and test strategy.
3. Applicable law and policy, including Revised Section 508 requirements for federal ICT.
4. Invoked military standards, interface standards, and data-item descriptions.
5. Public reference implementations and community guides.
6. This prototype baseline.

The interface must never treat a public example or an attractive design convention as authority over a program-selected requirement.

## 3. Human systems integration

### DoDI 5000.95, Human Systems Integration in Defense Acquisition

The instruction establishes HSI as a disciplined, integrated acquisition activity intended to optimize total system performance and minimize life-cycle cost. It covers human factors engineering, manpower, personnel, training, safety and occupational health, force protection and survivability, and habitability.

Design consequence: the human, software, procedures, training, environment, and support documentation form one system. An interface increment is incomplete when it is technically deterministic but has no task model, user-role model, error-recovery model, or representative-user evaluation plan.

### MIL-STD-1472, Human Engineering

The active standard establishes general human-engineering design criteria for military systems, subsystems, equipment, and facilities. Applicability and tailoring belong to the program.

Design consequence: preserve explicit modes, compatible control-display relationships, visible feedback, error prevention and recovery, readable information hierarchy, bounded critical actions, and evaluation in the intended environment. Formal compliance is not claimed until the applicable revision is tailored and evaluated by the responsible authority.

## 4. Federal accessibility

### Revised Section 508 Standards

Federal ICT includes software, electronic content, and support documentation. Applicable provisions are selected by the acquiring agency. Web and software content generally require evaluation against the incorporated WCAG Level A and AA criteria, applicable software provisions, functional-performance criteria, and support-documentation provisions.

### Prototype and pilot expectations

Public Section508.gov guidance distinguishes prototypes from pilots. A prototype should contain enough real navigation, controls, status, and component structure to show that accessibility is achievable. A pilot is expected to undergo formal conformance testing before rollout.

Design consequence: retain semantic structure, complete keyboard paths, visible focus, status announcements, color-independent meaning, accessible documentation, feature inventory, preliminary observations, and a formal test plan. Do not issue an Accessibility Conformance Report from untested assumptions.

## 5. C2SIM expectations

### SISO-STD-019-2020, Command and Control Systems - Simulation Systems Interoperation

The standard defines the interoperable message boundary. This rehearsal uses a public C2SIM reference artifact for unclassified test and rehearsal only.

### OpenC2SIM reference ecosystem

The public project distributes distinct artifacts for the GUI editor, C2 user control, initialization tooling, reference server, sandbox, client libraries, and role-specific user guides. That separation indicates different operator tasks and responsibilities rather than one universal interface.

Design consequence: this station does not imitate the C2SIM editor or a tactical common operating picture. It presents only the test-conductor and evaluator tasks required to exercise the authority sidecar around a standards-valid exchange. Initialization, order, report, server state, transport, authority, and verification remain distinguishable objects.

## 6. Software documentation data-item descriptions

The following active DIDs shape the working document set:

- DI-IPSC-81443, Software User Manual: hands-on use and position- or task-specific operation.
- DI-IPSC-81436, Interface Design Description: interface characteristics and controlled interface-design decisions.
- DI-IPSC-81438, Software Test Plan: test environment, planned qualification tests, schedule, and acquirer assessment of adequacy.
- DI-IPSC-81440, Software Test Report: qualification-test record for acquirer assessment.
- DI-IPSC-81442, Software Version Description: exact delivered version, contents, installation, and known limitations.

Design consequence: support documentation is organized by user role and acquisition decision. The documents are DID-shaped working artifacts, not contractual data items unless the contract invokes and tailors them.

## 7. Resulting interaction contract

The station therefore uses the following interaction contract:

1. **Plan** makes the scenario objective, expected result, pass condition, procedure, and initial conditions explicit before execution.
2. **Run** exposes only server-authorized actions, the next expected action, communications state, authority state, transport state, and persistent recovery guidance.
3. **Evaluate** compares expected and observed behavior and requires detached replay before acceptance.
4. **Evidence** preserves exact identities and the action ledger without forcing ordinary operators to interpret raw JSON.
5. **Guide** routes each role to task-specific support documentation.
6. Critical or terminal actions require confirmation.
7. Color never carries meaning alone.
8. A refusal remains visible with a code, explanation, and recovery.
9. The browser does not implement authority rules or receive C2SIM XML payloads.
10. Human-performance, accessibility, target-hardware, and operational qualification remain explicit future gates.

## 8. Review trigger

Revisit this baseline whenever the program changes its target users, operational mode summary, mission profile, selected standards, target hardware, acquisition pathway, invoked DIDs, accessibility requirements, or acceptance authority.
