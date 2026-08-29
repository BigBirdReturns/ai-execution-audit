# RPM Agent Evidence Membrane 01

## Classification

`RPM Agent Evidence Membrane 01` is a public, body-free supplier structural preflight and clean-room hardening contract for the exact `ronit22203/medical-multiturn-assistant` source tree frozen below. It is not a fork, clinical protocol, medical-device submission, deployment package, runtime authorization, or claim that the supplier application is safe for patient use.

The membrane accepts one exact public Git coordinate, performs static inspection without importing or executing supplier code, and emits one content-addressed structural-preflight receipt. It also supplies reusable deterministic primitives for effect provenance, telemetry lineage, and required-device completion. Those primitives are original Estate-side reference code. They do not silently patch the supplier tree and they acquire no authority merely by existing.

## Actors

The supplier is `ronit22203/medical-multiturn-assistant`. Its useful architectural proposition is that probabilistic inference should perform language work while Python owns workflow progression and safety interception.

The Estate qualifier owns source custody, static semantic inspection, finding classification, terminal derivation, and body-free public projection. It never imports the supplier package, opens a model endpoint, starts Streamlit, loads patient data, invokes a tool, or evaluates clinical correctness.

An external adapter, which does not yet exist in the supplier tree, must own identity verification, device pairing, support-ticket creation, nurse escalation, and any other claimed real-world effect. The adapter may report completion only after receiving an independently identifiable acknowledgement from the system that owns the effect.

A separate clinical authority must own threshold selection, predicate approval, patient-facing emergency language, jurisdiction, versioning, and change control. Neither the supplier model nor this membrane may mint that authority.

## Frozen source coordinate

```text
repository:
ronit22203/medical-multiturn-assistant

commit:
a0d32d3dcb1b39567df6bc02268b5452515c7e96

tree:
c926aa0720fc5d68be959ab502cca17388e7accc

commit status:
public_unlicensed_candidate

supplier code executed by qualification:
false

patient data processed by qualification:
false
```

The profile additionally freezes twelve critical Git blob identities covering the README, model configuration, safety rules, state graph, project metadata, evaluator, inference controller, UI telemetry path, interceptor, state machine, tool definitions, and tool registry. The qualifier derives the repository from the Git origin, observes one commit, derives the tree and critical blobs from that bound commit object, and materializes every relevant source, manifest, and test input from exact Git object bytes in a temporary directory. It does not read the mutable worktree or index. A repository, commit, tree, or critical-blob mismatch terminates `REFUSED`. A changed supplier tree requires a new profile and review transaction rather than inheriting this receipt.

## Closed terminals

Every static intake terminates as exactly one of:

```text
READY_FOR_RUNTIME_QUALIFICATION
HARDENING_REQUIRED
REFUSED
```

`READY_FOR_RUNTIME_QUALIFICATION` means the exact source tree satisfies this membrane's static structural gates for control ownership, provenance, transition integrity, telemetry separation, declared-rule coverage, evaluator shape, licensing, and authority binding. It authorizes only a separately receipted runtime campaign. It does not qualify the running control plane or establish that a medical claim, threshold, emergency instruction, device integration, clinical workflow, or external effect is correct.

`HARDENING_REQUIRED` preserves the exact source coordinate and names every failed hold gate. It authorizes no patient use and does not imply that the underlying architectural direction is unsound.

`REFUSED` means source custody failed. Semantic findings from an unbound tree cannot be promoted into a qualification conclusion.

## Effect provenance contract

The reference module closes five effect classes:

```text
SIMULATED
OBSERVED
REQUESTED
ACKNOWLEDGED
REFUSED
```

A simulator may emit only `SIMULATED`. A local parser or sensor packet may emit `OBSERVED` only with an evidence reference. Calling an external system emits `REQUESTED`, also with request evidence, until that system returns an independently identifiable acknowledgement. Only `ACKNOWLEDGED` may set `externalEffectClaimed=true`, and it requires both the request evidence and external acknowledgement reference. `REFUSED` carries no positive effect claim.

This prevents a local function returning `{"status": "success"}` from becoming evidence that an identity was verified, a device was paired, a support ticket was created, or a nurse was notified. The distinction is operational rather than cosmetic because downstream DFA progression and public status must depend on the receipt class, not on optimistic wording inside a Python dictionary.

## Telemetry lineage contract

The reference telemetry ledger closes four named source classes:

```text
DEVICE_OBSERVED
PATIENT_REPORTED
SIMULATED
MODEL_DERIVED
```

`MODEL_DERIVED` is explicitly refused as evidence. Each accepted observation is indivisible and carries one source class, one evidence reference when evidence exists, one sequence, and one set of scalar readings. A lineage snapshot retains the latest complete observation in each accepted source lane while leaving `selectedObservationId` and `selectionPolicyRef` unset. The ledger therefore separates provenance without inventing a universal clinical priority rule.

This closes two current failure modes. A patient-reported SpO2 value can no longer inherit a random pulse from the simulator, and a number repeated or invented by the language model can no longer become telemetry merely because it appears in assistant prose. A later consumer that selects one lane must bind that choice to an explicit policy rather than inheriting hidden precedence from this module.

## Transition contract

The reference transition guard owns the complete required-device denominator and consumes typed effect receipts. A device must be declared, successfully checked through an `OBSERVED` or `ACKNOWLEDGED` operational receipt, and then paired through an `ACKNOWLEDGED` receipt. `REQUESTED` cannot advance operational state. `SIMULATED` can advance only inside an explicitly constructed `SIMULATION` workflow. Education remains unavailable until:

```text
required_devices.issubset(paired_devices)
```

Every check and pairing step emits a transition receipt containing the consumed effect receipt, workflow mode, complete required, checked, and paired sets, per-device receipt identities, the derived completion predicate, and the next state. Pairing one of four declared devices therefore cannot satisfy a four-device workflow.

## Declared safety-rule coverage

This membrane does not decide whether any clinical threshold is appropriate. It requires the supplier to make the declared predicate denominator explicit and complete:

```text
diastolic_bp.max
diastolic_bp.min
heart_rate.max
heart_rate.min
spo2.max
spo2.min
systolic_bp.max
systolic_bp.min
```

A future supplier tree must bind each predicate to a named executable evaluator, named hostile tests that actually exist in the source tree, and one versioned clinical-authority reference in `configs/safety_rule_coverage.json`. The separate `configs/clinical_authority.json` object must identify the governing authority, jurisdiction, version, effective date, and approved predicate denominator. Passing these structural gates would prove that the implementation and tests cover the declared rule surface. It would not validate the medical content of that surface.

## Current exact assessment

The frozen source coordinate terminates:

```text
HARDENING_REQUIRED
```

The closed finding denominator is:

```text
CLINICAL_AUTHORITY_UNBOUND
EFFECT_PROVENANCE_CONTRACT_MISSING
EVALUATOR_EMPTY
EXTERNAL_EFFECT_ACKNOWLEDGEMENT_MISSING
LICENSE_UNDECLARED
MODEL_TEXT_ACCEPTED_AS_TELEMETRY
REQUIRED_DEVICE_COMPLETION_NOT_ENFORCED
SAFETY_COVERAGE_MANIFEST_MISSING
SIMULATED_TELEMETRY_UNTYPED
```

The findings have distinct mechanisms. The source publishes no license. Tool functions emit success-shaped local objects without effect classes or external acknowledgement receipts. The required-device set does not guard the transition to education. Random simulator values enter measurement-shaped results without typed simulation provenance. The UI parses assistant text into telemetry. The declared safety-rule surface has no complete evaluator-to-test coverage manifest or clinical-authority binding. The advertised evaluator exists as a zero-byte file.

These findings do not erase the supplier's useful architecture. They identify the exact seams where a deterministic wrapper can still launder simulation, model speech, or local intent into operational fact.

## Integration sequence

The supplier can consume the Estate primitives without changing its basic architecture.

First, the supplier should add `configs/effect_provenance.json` with the closed six-operation denominator, implementation bindings, permitted effect classes, acknowledgement requirements, and named tests. Every bound tool implementation should construct `estate/effect-receipt@1`. Mock functions remain available for demonstrations, but they must terminate `SIMULATED`. Identity verification, pairing, ticket creation, and nurse escalation remain `REQUESTED` until the owning external system acknowledges them.

Second, DFA transitions should consume validated effect receipts. Pairing progression should require an acknowledged or explicitly simulated effect according to the active environment, while the transition into education should require the complete declared device denominator.

Third, the telemetry pane should consume only the typed ledger. Patient reports and device packets may be displayed with provenance. Simulator records remain visibly simulated. Assistant messages are display text and never evidence.

Fourth, the supplier should implement the committed evaluator and emit `rpm-agent/evaluation-receipt@1` over a frozen case denominator. At minimum, the receipt should separately report red-flag recall, state-transition precision, tool-schema adherence, false escalation rate, and provenance violations. Metric claims without the receipt remain unavailable.

Fifth, a qualified clinical reviewer should provide the versioned authority object and approve the predicate and message denominator. The Estate can then verify binding and coverage while continuing to hold the clinical merits outside its own authority.

## Runtime campaign after static closure

A later physical campaign should use one RTX 3090-class seat for the Qwen2.5-7B runtime and an independent CPU verifier. It should not pool independent GPU memory merely to satisfy a small model. A second cell should replay the same immutable conversation and adapter fixtures under a different model or model-disabled NLG path.

The campaign question is whether the effect receipts, state transitions, telemetry ledger, safety-interceptor terminal, and public status remain invariant when the language model changes, emits malformed tool calls, repeats safety text, disappears mid-turn, or returns adversarial prose. The model outputs may differ linguistically. The authority-bearing trace must not.

No runtime campaign is authorized by this source-only contract. Physical seat qualification, model artifact binding, external adapter integration, patient-data governance, clinical review, and representative operator qualification remain separate transactions.

## Permanent product paths

```text
.github/workflows/rpm-agent-evidence-membrane-01.yml
mating_surface/anchor_node/RPM-AGENT-EVIDENCE-MEMBRANE-01.md
mating_surface/anchor_node/rpm-agent-evidence-membrane-profile-01.json
mating_surface/anchor_node/rpm-agent-evidence-membrane.ps1
mating_surface/anchor_node/rpm_agent_effects.py
mating_surface/anchor_node/rpm_agent_estate_qualifier.py
mating_surface/anchor_node/verify_rpm_agent_estate_bootstrap.py
mating_surface/anchor_node/verify_rpm_agent_estate_receipt.py
mating_surface/anchor_node/conformance/test_rpm_agent_evidence_membrane.py
```

The measured bootstrap authenticates the profile, reference effect module, qualifier, and detached verifier before executing the qualifier. The detached verifier reconstructs the terminal, claims, public projection, source binding, and receipt identity rather than trusting stored semantics. The permanent 36-witness denominator covers repository-origin drift, commit and tree drift, staged-index substitution, dirty-worktree substitution, Git symlink modes, terminal forgery, fully re-signed claim promotion, measured-file substitution, comment-marker spoofing, phantom evaluator bindings, model-prose telemetry, simulator field laundering, premature device completion, unchecked pairing, requested-effect promotion, implicit simulation, and unacknowledged external-effect promotion.

## Claim boundary

```text
exact public source bound: true
supplier source executed: false
patient data processed: false
current static terminal: HARDENING_REQUIRED
control plane structurally ready: false
runtime qualification required: true
control plane qualified: false
clinical safety qualified: false
clinical efficacy qualified: false
external effects observed: false
runtime campaign executed: false
physical Estate qualified: false
representative operator qualified: false
clinical authority: none
operational authority: none
medical authority: none
mission authority: none
command authority: none
targeting / engagement / effector / weapons capability: false
```

## Control question

Does this exact membrane prevent mock success objects, random simulator fields, assistant prose, partial device completion, empty or marker-only evaluators, phantom bindings, unbound clinical rules, and source-coordinate drift from manufacturing structural readiness, runtime qualification, or clinical authority, while leaving Ronit's deterministic controller architecture intact enough to accept real adapters and evidence later?
