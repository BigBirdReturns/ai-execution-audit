# Scenario Catalog and Acceptance Evaluation

## 1. Purpose

The rehearsal station treats a test scenario as a controlled acceptance object, not as explanatory browser copy. The source-controlled scenario catalog defines what is being tested, which initial conditions apply, which actions constitute the procedure, which observations must be made, and what result is required for acceptance.

This document explains the catalog, the server-owned evaluation contract, and the change-control rules that prevent the presentation layer from manufacturing a pass.

## 2. Authoritative objects

Each qualified scenario is defined in `mating_surface/rehearsal_console/scenarios.mjs` and carries:

- a stable `scenarioId` and explicit revision;
- a content-addressed `scenarioDefinitionId`;
- classification and rehearsal boundary;
- objective, expected outcome, and pass condition;
- complete initial configuration;
- ordered procedure steps with bounded inputs;
- machine-evaluated acceptance checks.

The full set carries a content-addressed `scenarioCatalogId`. The loopback host exposes the catalog through `GET /api/scenarios`. The browser renders that response but does not contain a second scenario table or acceptance implementation.

## 3. Execution and evaluation sequence

```text
source-controlled scenario definition
        ↓
clean session initialized with scenario ID and configuration
        ↓
server records the exact user-action ledger
        ↓
canonical authority and transport runtimes execute the actions
        ↓
server compares procedure, configuration, and observed state
        ↓
content-addressed scenario evaluation
        ↓
exported session receipt and detached replay verification
```

The browser may select a scenario, request a reset, submit a server-enabled action, and render the returned state. It cannot alter the scenario definition, define a new pass condition, calculate the acceptance result, or promote a variation into a qualified run.

## 4. Evaluation statuses

### Pass

`pass` means all of the following are true:

- the exact qualified initial configuration was used;
- the recorded actions completed the source-controlled procedure;
- no unplanned action or incompatible input was introduced;
- every machine-evaluated acceptance check passed;
- the resulting evaluation identity is bound into the state and session receipt.

A pass remains subject to detached replay. It does not grant operational authority or establish operational suitability.

### Fail

`fail` means the qualified procedure completed without a configuration or procedure deviation, but one or more expected observations did not match the recorded state.

### Incomplete

`incomplete` means the qualified procedure has not yet been completed. A partially executed run cannot be accepted merely because its current state appears favorable.

### Deviated

`deviated` means the initial configuration differed from the qualified baseline or the action ledger departed from the specified procedure. The station retains the observed checks for analysis, but sets `acceptanceEligible` to false even when those checks happen to match the nominal expected values.

A deviation is evidence. It is never silently normalized into a pass.

## 5. Qualified versus exploratory operation

The Plan view may be used to examine different conditions, but any change from the selected scenario's controlled configuration creates an exploratory variation. The server records each changed field and the resulting evaluation is `deviated` or `incomplete`, not `pass`.

A useful exploratory result can become a qualified scenario only through source review:

1. assign a new scenario ID or revision;
2. state the objective and pass condition;
3. define the complete configuration and ordered procedure;
4. define machine-evaluated checks;
5. run positive, negative, tamper, and detached-replay tests;
6. review the documentation and traceability impacts;
7. promote the revised content-addressed catalog through CI.

## 6. Receipt closure

The interactive state and exported receipt bind:

- `scenarioCatalogId`;
- `scenarioId`;
- `scenarioDefinitionId`;
- `stateCoreId` and final state ID;
- `evaluationId`, status, checks, and deviations;
- initial configuration;
- exact user-action ledger;
- canonical authority and transport receipts;
- source provenance.

Detached verification reconstructs the same scenario from the packaged catalog, replays the same actions through the same runtime identities, and refuses a changed catalog, scenario definition, configuration, action order, action input, evaluation identity, or final state identity.

## 7. Role responsibilities

### Test conductor

Select the qualified scenario, verify the baseline conditions, follow the prescribed procedure, and preserve deviations without attempting to correct the run after the fact.

### Operator or mission SME

Assess whether the scenario, expected consequence, action feedback, and recovery guidance support correct understanding. The SME does not determine the software acceptance result.

### Evaluator

Review the server-produced status and checks, run detached verification, and classify the run for the test record.

### V&V reviewer

Confirm catalog and scenario identities, reconstruct the evaluation, and verify that the browser did not supply acceptance logic.

### Integrator

Replace the reference message source at the selected standard port while preserving the scenario and evaluation boundary or introducing an explicitly reviewed new profile.

## 8. Change control and claim boundary

The source-controlled catalog is the current rehearsal acceptance basis. A program contract, statement of work, approved test plan, controlled standard profile, or acceptance authority may replace or tailor it. Browser text, provider marketing, and ad hoc operator preference may not.

The current catalog covers unclassified, deterministic rehearsal cases over a public C2SIM reference artifact. It does not qualify a fielded system, representative operator population, operational message profile, command authority, targeting, engagement, effector control, execution path, or weapons capability.
