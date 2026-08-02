# UI and Documentation Implementation Note

The rehearsal station is structured as a role- and task-oriented acceptance instrument. The browser does not implement authority policy. It selects source-controlled scenarios, requests actions, renders server-owned receipts and acceptance evaluations, exposes evidence, and routes each user role to the relevant document.

The interaction sequence is:

```text
Plan -> Run -> Evaluate -> Evidence
                   \-> Guide
```

The header separately exposes run lifecycle, communications condition, and authority disposition. Actions are enabled from the server-returned control contract. Critical actions require confirmation. Each request produces persistent feedback, visible processing state, and recovery instructions when refused. Evaluation is computed by the server from the content-addressed scenario definition and distinguishes pass, fail, incomplete, and deviated before detached replay. Browser code contains no acceptance checks. Evidence preserves exact source, artifact, message, event, and session identities without placing the C2SIM XML payload in browser state.

The documentation set is role-specific and DID-shaped. It supports operators, test conductors, evaluators, V&V reviewers, integrators, accessibility and HSI reviewers, test leads, and configuration managers. Formal human-engineering, Section 508, representative-user, target-hardware, operational, and contractual-data-item qualification remain outside the current evidence tier.
