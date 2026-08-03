# Software Test Report

## 1. Purpose

This report records the current qualification baseline. It is shaped by DI-IPSC-81440, Software Test Report, and is not a contract data item unless explicitly invoked and tailored.

## 2. Baseline under test

The controlling source is the most recent production commit recorded in the packaged build manifest. The station directly imports the canonical authority runtime server-side and uses the retained public C2SIM rehearsal evidence. External evidence produced outside that runtime is admitted separately and cannot inherit the canonical scenario result.

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

The scenario-catalog increment further established a content-addressed source catalog, server-owned pass/fail/incomplete/deviated evaluation, catalog and definition tamper refusal, and detached replay closure over the evaluation identity.

The evaluator increment further established a separate local accept, reject, or defer receipt; Ed25519 process-signature integrity; exact session and automatic-evaluation binding; immutable one-disposition custody; and refusal to accept an automatic fail, incomplete, or deviated result. The ephemeral signer does not authenticate organizational identity or establish program acceptance authority.

## 4. HSI and documentation increment

The HSI increment added:

- Plan, Run, Evaluate, Evidence, and Guide work areas;
- explicit separation of run, communications, and authority state;
- source-controlled qualified scenario cards with objective, expected result, pass condition, procedure, and machine checks;
- next-action runbook guidance;
- persistent action result, reason, and recovery;
- confirmation for isolation, returning-authority classification, and resetting a started run;
- server-owned expected-versus-observed matrix and visible deviation classification;
- persistent verification and export results;
- role-based support documentation;
- keyboard-operable work-area tabs;
- color-independent text and symbol cues;
- mobile single-column operation.

## 5. External standing-orders evidence increment

One private external event log and one producer report were supplied outside the canonical session runtime. Their raw bytes remain outside the public repository. The retained receipt binds only their byte counts, SHA-256 identities, bounded observations, claim dispositions, and next-evidence requirements.

```text
controlling event log
bytes:   5,122
sha256:  fd408eac2c7743e7cc17058242a5b5ecbc8baaf6441c7af826aa7db2512bb575

producer report under review
bytes:   17,758
sha256:  2217491042db3001b21c60dce55e9d82156ffe862b9e34768004e46f7e81685a
```

The controlling log identifies an admin TEST ONLY injection path and expressly excludes Lattice auto-detection. Its exact injected DOWN-to-UP interval is 25,505 ms.

```text
presented synthetic threats:             15
retained decisions:                      15
SMALL_UAS marked in-list → AUTHORIZE:    10 / 10
MEDIUM_UAS marked out-of-list → SAFE_DENY: 5 / 5
presented mapping deviations:             0
feed-to-decision log interval:            1–29 ms
median:                                  26 ms
mean:                                    18.467 ms
nearest-rank p95:                        29 ms
maximum:                                 29 ms
```

These are scripted harness log intervals, not end-to-end network, Lattice, engagement, effector, or weapon-effect latency.

The log also retains `RECONCILE_ACK last_ack=15` and raw `so_period_cleared=0`. No completion meaning is inferred without a field contract, receiver accepted/rejected/duplicate sets, and detached replay.

## 6. Claim dispositions

```text
local allowlist decision behavior       pass
admin-injected communications change    pass within harness
signed bounded authority                incomplete
duplicate or replay refusal             not run
returning-authority supersession        incomplete
reconciliation completion               incomplete
operator and separate link witnesses    not witnessed
end-to-end authority transaction        incomplete
operational or human-factors result      not acquired
```

Eight claims are required for end-to-end acceptance. One is a complete pass and seven remain incomplete or unwitnessed. No required claim failed in the presented sample, but exact canonical closure is absent.

```text
canonical scenario catalog bound:       no
scenario definition bound:              no
session receipt bound:                  no
session verification bound:             no
detached replay status:                  absent
automatic result:                        incomplete
acceptance eligible:                     false
```

Controlling result:

> Synthetic local allowlist decision behavior passed. End-to-end denied-communications authority acceptance remains incomplete.

## 7. Producer-report review

The producer report correctly describes the admin injection, the ten allowlisted authorizations, the five safe denials, and the presented mapping. It outruns the controlling log when it promotes an active-state Boolean into an authority signature, treats the injected interval as a signed lease, asserts independent headquarters/local-link and operator-presence witnesses, imports an unwitnessed epoch identity, asserts replay or explicit returning-authority supersession, interprets acknowledgement as full reconciliation, or concludes that operational capability is ready.

The external-evidence verifier therefore refuses raw-source publication, digest tampering, undeclared fields, pass without cited observations, caller-promoted automatic status, and closure borrowed from another source evidence set. The normal pack builder also verifies that the retained receipt remains private-digest-only, automatically incomplete, and acceptance-ineligible.

## 8. Interpretation

Passing automated checks establishes source, receipt, and interaction-contract consistency. It does not establish that representative warfighters can use the station effectively under operational workload. The external receipt establishes bounded behavior inside a scripted admin-inject harness; it does not establish signed authority custody, physical network partition, replay closure, returning-authority supersession, operational suitability, or human performance.

## 9. Open findings

- No canonical session reproduces the retained external source evidence set.
- No signed authority or lease identity, issuer, generation, validity, signature, or verification receipt is retained for that source.
- No duplicate message or receiver replay disposition is retained for that source.
- No returning authority generation or explicit supersession receipt is retained for that source.
- No independent operator-presence or separate headquarters/local-link witness is retained for that source.
- No receiver accepted, rejected, and duplicate closure or detached replay is retained for that source.
- No formal Section 508 conformance report exists yet.
- No formal MIL-STD-1472 compliance assessment exists yet.
- No representative operator cohort has completed timed scenarios.
- No physical target, gloved input, low-light, vibration, or degraded-display test has been run.
- No operational C2SIM profile or controlled tactical standard artifact has entered the harness.
- No Polybolos or other provider implementation has entered the standards port.
