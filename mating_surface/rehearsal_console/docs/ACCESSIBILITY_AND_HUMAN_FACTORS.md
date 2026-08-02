# Accessibility and Human-Factors Engineering Plan

## 1. Status

This document records prototype alignment and the remaining evaluation plan. It does not claim formal Section 508 or MIL-STD-1472 conformance.

## 2. Governing public references

- MIL-STD-1472, Human Engineering, active revision H with 2026 validation notice.
- DoD Human Systems Integration policy and guidance.
- Revised Section 508 Standards and WCAG Level A and AA criteria incorporated by reference.
- GSA prototype and pilot accessibility guidance.
- GSA Accessibility Conformance Report guidance.

## 3. Design responses

### Task and role separation

The interface is organized by test-conductor workflow: Plan, Run, Evaluate, Evidence. Guide provides role-specific support. This avoids forcing operators, evaluators, and integrators into one undifferentiated dashboard.

### Explicit state dimensions

Run lifecycle, communications state, and authority disposition are displayed independently. Each state uses text, a lettered or symbolic marker, border treatment, and color. Color is never the sole cue.

### Feedback and error recovery

Each action yields persistent feedback. Refusals display an application-level code, a plain-language explanation, and a recovery instruction. Feedback remains until a later action replaces it.

### Critical actions

Isolation, returning-authority classification, and resetting a started run require explicit confirmation.

### Progressive disclosure

Human-readable findings are primary. Exact IDs and JSON remain available in Evidence. This supports rapid use without removing audit detail.

### Keyboard and focus

Work-area tabs support Arrow keys, Home, and End. All controls are native keyboard-operable elements. Dialog focus is managed by the browser. Persistent feedback is focusable after an action.

### Responsive layout

The desktop view supports simultaneous conductor, state, and action work. The mobile layout becomes a single-column station with large controls and preserved work-area navigation.

## 4. Prototype evidence to retain

- feature and component inventory;
- keyboard navigation results;
- focus order and visible-focus screenshots;
- color and contrast measurements;
- screen-reader output notes;
- error and recovery examples;
- critical confirmation examples;
- mobile and desktop screenshots;
- documentation accessibility review;
- defect and remediation log.

## 5. Formal evaluation still required

1. Determine the applicable Revised Section 508 provisions using the agency accessibility requirements process.
2. Execute a repeatable application test method, such as the DHS Trusted Tester process when selected by the acquirer.
3. Produce an Accessibility Conformance Report or OpenACR when required.
4. Conduct human-factors evaluation with representative users, tasks, workload, environment, and equipment.
5. Measure task success, wrong-action rate, recovery time, scenario time, comprehension of authority state, and subjective workload.
6. Reevaluate on target hardware, including display size, input device, lighting, vibration, noise, and any protective equipment.

## 6. Failure conditions

The interface is not acceptable when a user must infer authority from color, cannot find the next action, cannot distinguish link state from decision state, cannot retain an error long enough to recover, can activate a critical action without confirmation, or must inspect raw JSON to understand a refusal.
