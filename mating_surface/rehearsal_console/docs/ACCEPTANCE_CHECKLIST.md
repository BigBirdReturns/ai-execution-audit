# Human-System Acceptance Checklist

Use this checklist during representative-user and target-environment evaluation. It is a test aid, not a substitute for the approved test plan.

## Before the run

- [ ] The user can identify the object as a rehearsal and acceptance station rather than an operational command product.
- [ ] The user can identify the selected scenario objective, expected result, pass condition, and initial conditions.
- [ ] The user understands which controls require reset and which can change during a run.
- [ ] The test conductor has recorded the user role, environment, hardware, display, input devices, accessibility needs, and deviations.

## During the run

- [ ] The user can distinguish run lifecycle, communications state, and authority disposition.
- [ ] The next recommended action is visible without reading the event ledger.
- [ ] Enabled and disabled actions agree with the server-returned control contract.
- [ ] Every action provides persistent feedback.
- [ ] A delayed request shows visible processing status and blocks repeated activation.
- [ ] A refusal gives a code, plain-language explanation, and recovery instruction.
- [ ] Critical or terminal actions require confirmation.
- [ ] Status remains understandable without relying on color alone.
- [ ] Keyboard focus remains visible and reaches all required controls.

## Evaluation

- [ ] Expected and observed results are shown together.
- [ ] Pass, fail, and incomplete are distinguishable.
- [ ] A replay refusal is distinguishable from an authority refusal.
- [ ] Safe state and human-required return are understandable to the representative user.
- [ ] Detached verification can be initiated and its result persists.

## Evidence

- [ ] The user can locate source identity, artifact identity, semantic conversation identity, event history, and machine receipt.
- [ ] The exported receipt replays to the same final identity.
- [ ] Browser state does not expose standard XML payloads.
- [ ] The session record includes test identity, participant role, environment, deviations, findings, and final disposition.

## Closeout

- [ ] Findings are classified as interface defect, documentation defect, training need, environment dependency, standard-profile issue, authority-policy issue, or test-procedure issue.
- [ ] Unresolved findings have an owner and retest criterion.
- [ ] No prototype result is described as operational qualification without the required target-system evidence.
