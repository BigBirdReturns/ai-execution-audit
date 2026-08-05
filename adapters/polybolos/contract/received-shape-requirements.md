# Received shape requirements

A confirmed adapter requires one authorized representative shape from Polybolos. Source code is not required. The fixture may be anonymized and synthetic, but its field names, nesting, types, units, and identity rules must match the actual producer boundary.

The minimum fixture must establish:

- request and trace identity;
- producer and exact build identity;
- candidate creation time and deadline;
- action-class vocabulary;
- Command Intelligence entity-reference semantics;
- candidate-specific values;
- reason-code and timing semantics where exported;
- unknown-field behavior;
- restart and replay behavior;
- the intended destination for AXM status receipts.

For every field, the mapping review records whether translation is exact, normalized, one-way, intentionally omitted, or rejected. No missing field receives a guessed default.

The adapter remains `provisional` until a Polybolos maintainer confirms the mapping. A provisional map may run only against synthetic fixtures and cannot enter the live authority path.
