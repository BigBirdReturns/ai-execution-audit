# UI, Documentation, and Test Traceability Matrix

| ID | Requirement | Source or UI element | Verification |
| UX-001 | Separate setup from execution | Plan and Run work areas | DOM and browser workflow test |
| UX-002 | Make expected result explicit before action | Scenario card objective, expected result, pass condition | Scenario-card source test |
| UX-003 | Separate run, communications, and authority state | Header chips and three state planes | DOM assertion and screenshot review |
| UX-004 | Show next expected action | Runbook and current-instruction panel | Procedure progression test |
| UX-005 | Use server-owned enabled-action state | `state.controls` rendered by browser | Source test and API exercise |
| UX-006 | Provide persistent action feedback | `actionFeedback` region | Positive and refusal browser tests |
| UX-007 | Explain error and recovery | Error code, message, recovery map | Refusal tests |
| UX-008 | Confirm critical or terminal actions | Native dialog for isolate, reconcile, and reset | DOM and browser interaction test |
| UX-009 | Avoid color-only meaning | Text, symbols, borders, and color | Palette and semantic-cue tests |
| UX-010 | Support keyboard navigation | Native controls and tab-list key handling | Keyboard interaction test |
| UX-011 | Present human-readable evidence before exact IDs | Evaluate and Evidence work areas | Screenshot and DOM review |
| UX-012 | Keep C2SIM XML out of browser state | Public state minimization | CI JSON audit |
| UX-013 | Verify exported sessions through the canonical runtime | `/api/verify` and verifier result | Detached replay test |
| UX-014 | Package task-specific support documentation | `docs/` tree and Guide links | Documentation inventory test |
| UX-015 | Preserve visible claim boundary | Header subtitle, footer, docs | Source and rendered DOM test |
| UX-016 | Keep scenario definitions outside browser code | `scenarios.mjs` and `/api/scenarios` | Source and API contract tests |
| UX-017 | Compute acceptance server-side | `state.evaluation` from session conductor | Scenario evaluator and detached replay tests |
| UX-018 | Prevent exploratory variation from passing | Configuration and procedure deviation ledger | Positive and negative scenario tests |
| UX-019 | Bind catalog, definition, evaluation, and state identities | State and exported receipt v2 | Tamper and replay tests |
| DOC-001 | Hands-on user instructions | `USER_GUIDE.md` | Documentation inventory |
| DOC-002 | Position or task quickstart | `OPERATOR_QUICKSTART.md` | Documentation inventory |
| DOC-003 | Test conduct procedure | `TEST_CONDUCTOR_GUIDE.md` | Documentation inventory |
| DOC-004 | Interface ownership and message boundary | `INTERFACE_DESIGN_DESCRIPTION.md` | Documentation review |
| DOC-005 | Test environment, cases, and acceptance gates | `TEST_PLAN.md` | Documentation review |
| DOC-006 | Executed results and remaining tests | `TEST_REPORT.md` | Documentation review |
| DOC-007 | Accessibility and HFE plan | `ACCESSIBILITY_AND_HUMAN_FACTORS.md` | Documentation review |
| DOC-008 | Exact source and known limitations | `VERSION_DESCRIPTION.md` | Build-manifest audit |
| DOC-009 | Scenario catalog and acceptance contract | `SCENARIO_CATALOG_AND_ACCEPTANCE.md` | Documentation inventory and link test |
| --- | --- | --- | --- |
