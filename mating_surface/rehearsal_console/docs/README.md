# Rehearsal Console Documentation Set

## Purpose

This documentation set supports a local, unclassified, standards-based denied-communications authority rehearsal. The station is a test and acceptance instrument. It is not a tactical common operating picture, a vendor product interface, or an operational command path.

The documents are organized around the people who use the station and the evidence an acquirer or evaluator needs to assess it. They are shaped by active DoD software data-item descriptions and public human-factors and accessibility guidance, but they are not contractual data items unless a contract explicitly invokes and tailors them.

## Role map

| Role | Primary document | Primary task |
| --- | --- | --- |
| Test conductor | `TEST_CONDUCTOR_GUIDE.md` | Select, execute, and record a qualified scenario |
| Operator or mission SME | `OPERATOR_QUICKSTART.md` | Assess whether actions, outcomes, and recovery guidance are understandable |
| Hands-on user | `USER_GUIDE.md` | Operate Plan, Run, Evaluate, Evidence, and Guide work areas |
| V&V reviewer | `VERIFIER_GUIDE.md` | Reconstruct source, message, transport, authority, and session identities |
| Integrator | `INTERFACE_DESIGN_DESCRIPTION.md` | Replace the reference fixture at a program-selected standard port |
| Test lead or acquirer | `TEST_PLAN.md` and `TEST_REPORT.md` | Assess planned coverage and executed results |
| Accessibility or HSI reviewer | `ACCESSIBILITY_AND_HUMAN_FACTORS.md` and `REFERENCE_BASELINE.md` | Review governing public references, prototype accessibility, and human-performance evidence |
| Configuration manager | `VERSION_DESCRIPTION.md` | Identify the exact source, dependencies, evidence, and known limitations |

## Document status

| Document | Status | Controlling evidence |
| --- | --- | --- |
| Operator quickstart | Baseline | Interactive console workflow |
| User guide | Baseline | Current source and qualified scenarios |
| Test conductor guide | Baseline | Seven deterministic scenario cases |
| Verifier guide | Baseline | Export and replay receipt chain |
| Interface design description | Baseline | Canonical runtime, loopback host, and standard-port boundary |
| Test plan | Baseline | GitHub qualification workflow and local negative controls |
| Test report | Baseline | Most recent qualified source commit and retained artifacts |
| Accessibility and HFE plan | Prototype alignment | Formal Section 508 and MIL-STD-1472 evaluation pending |
| Reference baseline | Baseline | Public HSI, accessibility, C2SIM, and DID authorities |
| Traceability matrix | Baseline | Requirement-to-source-to-test mapping |
| Version description | Baseline | Build manifest and source provenance |

## Governing claim boundary

The current evidence covers deterministic, unclassified rehearsal behavior over a public C2SIM reference artifact, a loopback-only host, a canonical authority runtime, and replayable receipts. It does not qualify an operational C2SIM profile, a fielded network, target hardware, a tactical user population, an external provider implementation, or any command, targeting, engagement, effector, execution, or weapons capability.
