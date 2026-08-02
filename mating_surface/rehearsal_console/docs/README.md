# Denied Communications Authority Rehearsal documentation

## Purpose

This documentation set supports the neutral loopback rehearsal station in `mating_surface/rehearsal_console`. The station is a test-conductor and evaluation instrument for a standards-valid C2SIM reference conversation plus an external authority sidecar. It is not a tactical common operating picture, a provider product interface, or an operational command system.

The documentation is organized by role because the operator, test conductor, verifier, and integrator need different information at different points in the workflow.

## Role map

| Role | Primary document | Main responsibility |
|---|---|---|
| Test conductor | `TEST_CONDUCTOR_GUIDE.md` | Select the case, establish initial conditions, execute the procedure, and record deviations |
| Operator or mission SME | `OPERATOR_QUICKSTART.md` | Judge whether actions, status, consequences, and recovery are understandable |
| General user | `USER_GUIDE.md` | Operate Plan, Run, Evaluate, Evidence, and Guide |
| V&V reviewer | `VERIFIER_GUIDE.md` | Reconstruct source, message, transport, authority, and session identities |
| Integrator | `INTERFACE_DESIGN_DESCRIPTION.md` | Replace the reference fixture at a selected standard port without moving authority logic into the browser |
| Test lead | `TEST_PLAN.md` and `TEST_REPORT.md` | Maintain qualification scope, procedures, results, and remaining tests |
| Accessibility and HSI reviewer | `HUMAN_SYSTEM_EXPECTATIONS.md` and `ACCESSIBILITY_AND_HUMAN_FACTORS.md` | Evaluate expected interaction doctrine and prototype evidence |
| Configuration manager | `VERSION_DESCRIPTION.md` | Maintain exact release inventory and claim boundary |

## Human-system baseline

`HUMAN_SYSTEM_EXPECTATIONS.md` records the role, workflow, state, feedback, confirmation, accessibility, documentation, and evidence patterns expected of a defense rehearsal and acceptance station. `REFERENCE_BASELINE.md` records the public DoD HSI, human-engineering, accessibility, C2SIM, and software-documentation sources used to shape those expectations.

## Workflow

The intended workflow is Plan, Run, Evaluate, then Evidence. Planning makes the objective, expected result, pass condition, and initial conditions visible before action. Running exposes only server-enabled actions and retains persistent result and recovery text. Evaluation compares expected and observed behavior and invokes detached replay. Evidence exposes exact receipts and source identities.

## Documentation status

These files are DID-shaped working artifacts. They follow the information architecture normally expected of a Software User Manual, Interface Design Description, Software Test Plan, Software Test Report, and Software Version Description. They are not represented as contract data items unless a contract or data-item list explicitly invokes the corresponding DID and tailoring.

## Claim boundary

The current evidence covers a loopback-only, unclassified rehearsal profile, one public C2SIM reference artifact, deterministic fault injection, direct server-side use of the canonical authority runtime, and replayable local receipts. It does not qualify an operational C2SIM profile, field network, Polybolos implementation, target MAME or MotionDeck installation, operational operator population, command authority, targeting, engagement, effector control, execution path, or weapons capability.
