# Silent dependency red team variant

This variant simulates a runtime that embeds scheduler and policy fingerprints into provenance
without making any network calls.

Why this matters:
- Many production stacks can be non-networked at runtime but still depend on scheduler policy,
  partition configuration, license gates, or proprietary control logic.
- The audit suite must fail loudly when these dependencies exist.

How to trigger:
- Set AI_AUDIT_SILENT_DEPENDENCY=1
- Optionally set AI_AUDIT_SCHEDULER_FINGERPRINT and AI_AUDIT_POLICY_HASH

The reference runtime will log an `embedded_dependency` event with these fields.
The vendor hint scanner will then reject the replay bundle.
