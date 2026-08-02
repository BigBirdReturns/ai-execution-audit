# Denied Communications Authority Rehearsal documentation

## Purpose

This documentation set supports the neutral loopback rehearsal station in `mating_surface/rehearsal_console`. The station is a test-conductor and evaluation instrument for a standards-valid C2SIM reference conversation plus an external authority sidecar. It is not a tactical common operating picture, a provider product interface, or an operational command system.

The documentation is organized by role because the operator, test conductor, evaluator, verifier, and integrator need different information at different points in the workflow.

## Role map

| Role | Primary document | Main responsibility |
|---|---|---|
| Test conductor | `TEST_CONDUCTOR_GUIDE.md` and `SCENARIO_CATALOG_AND_ACCEPTANCE.md` | Select the controlled case, establish initial conditions, execute the procedure, and preserve deviations |
| Operator or mission SME | `OPERATOR_QUICKSTART.md` | Judge whether actions, status, consequences, and recovery are understandable |
| General user | `USER_GUIDE.md` | Operate Plan, Run, Evaluate, Evidence, and Guide |
| Evaluator | `EVALUATOR_DISPOSITION.md` | Review automatic evidence, issue a separate accept/reject/defer disposition, and export the combined package |
| V&V reviewer | `VERIFIER_GUIDE.md` | Reconstruct source, message, transport, authority, session, and evaluator-disposition identities |
| Integrator | `INTERFACE_DESIGN_DESCRIPTION.md` | Replace the reference fixture and local evaluator signer without moving authority or acceptance logic into the browser |
| Test lead | `TEST_PLAN.md` and `TEST_REPORT.md` | Maintain qualification scope, procedures, results, and remaining tests |
| Accessibility and HSI reviewer | `HUMAN_SYSTEM_EXPECTATIONS.md` and `ACCESSIBILITY_AND_HUMAN_FACTORS.md` | Evaluate expected interaction doctrine and prototype evidence |
| Configuration manager | `VERSION_DESCRIPTION.md` | Maintain exact release inventory and claim boundary |

## Acceptance baseline

`SCENARIO_CATALOG_AND_ACCEPTANCE.md` describes the source-controlled scenario catalog, server-owned automatic evaluation, pass/fail/incomplete/deviated states, receipt closure, and scenario change-control process. The browser renders this contract but does not own it.

`EVALUATOR_DISPOSITION.md` describes the separate human disposition. A replay-verified automatic pass may be accepted, rejected, or deferred. A fail, incomplete, or deviated automatic result cannot be converted into an accepted qualified result by the local evaluator lane.

## Human-system baseline

`HUMAN_SYSTEM_EXPECTATIONS.md` records the role, workflow, state, feedback, confirmation, accessibility, documentation, and evidence patterns expected of a defense rehearsal and acceptance station. `REFERENCE_BASELINE.md` records the public DoD HSI, human-engineering, accessibility, C2SIM, and software-documentation sources used to shape those expectations.

## Workflow

The intended workflow is Plan, Run, Evaluate, then Evidence. Planning makes the objective, expected result, pass condition, and initial conditions visible before action. Running exposes only server-enabled actions and retains persistent result and recovery text. Evaluation renders the server-owned comparison between the selected source-controlled scenario and the observed state, then invokes detached replay. The separate evaluator workspace issues an immutable local disposition against that exact evidence. Evidence exposes the session receipt, verification, disposition, disposition verification, and combined acceptance package.

## Documentation status

These files are DID-shaped working artifacts. They follow the information architecture normally expected of a Software User Manual, Interface Design Description, Software Test Plan, Software Test Report, and Software Version Description. They are not represented as contract data items unless a contract or data-item list explicitly invokes the corresponding DID and tailoring.

## Claim boundary

The current evidence covers a loopback-only, unclassified rehearsal profile, one public C2SIM reference artifact, deterministic fault injection, direct server-side use of the canonical authority runtime, replayable local receipts, and local evaluator-disposition integrity. The ephemeral local signer does not authenticate evaluator identity or establish program acceptance authority. The estate does not qualify an operational C2SIM profile, field network, Polybolos implementation, target MAME or MotionDeck installation, operational operator population, command authority, targeting, engagement, effector control, execution path, or weapons capability.
