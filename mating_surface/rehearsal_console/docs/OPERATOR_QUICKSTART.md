# Operator Quickstart

## What this station is

The station demonstrates how authority behaves when communications degrade. It uses four schema-valid C2SIM rehearsal messages and an external authority sidecar. Your task is to observe whether the displayed action, disposition, reason, and recovery are understandable and operationally credible.

## Start a run

1. Open **Plan**.
2. Select a qualified scenario.
3. Read the objective, expected result, pass condition, and procedure.
4. Review the initial conditions.
5. Select **Start clean rehearsal**.

The station moves to **Run** and highlights the next expected action.

## Read the three state planes

- **Run lifecycle** tells you whether the scenario is ready, running, awaiting review, or complete.
- **Communications** tells you whether the node is connected, headquarters-denied, restored, or isolated.
- **Authority disposition** tells you the latest result: allow, hold, refuse, safe state, reconciled, or human decision required.

These states are deliberately separate. A connected link does not prove a message was authorized, and an authorized message does not prove that transport accepted it only once.

## Take an action

Use only enabled actions. The runbook shows the expected sequence. After each action, read the persistent feedback block:

- what action was recorded;
- what the runtime returned;
- why it returned that result;
- what to do next.

Isolation and returning-authority classification require confirmation because they materially change or close the scenario.

## Evaluate the result

Open **Evaluate** after the procedure. The visible matrix compares the selected scenario card with the observed state. Then select **Verify current session**. A passing replay means the exported action ledger reconstructs to the same final identity through the same canonical runtime.

## Preserve evidence

Open **Evidence** and select **Export session receipt**. The exported JSON contains the initial configuration, recorded test-conductor actions, runtime identities, receipt identities, and final state identity. It does not contain the C2SIM XML payloads.

## Stop conditions

Stop the run and notify the test conductor if:

- the enabled action does not match the runbook;
- the explanation does not match the displayed disposition;
- a critical action occurs without confirmation;
- an error disappears before it can be read;
- color is the only way to distinguish a state;
- the same message appears accepted twice;
- returning authority silently overwrites the partition history.
