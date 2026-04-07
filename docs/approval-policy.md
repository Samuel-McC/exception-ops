# Approval Policy

Initial policy:

- low risk:
  - auto-execution may be allowed later
  - still auditable

- medium risk:
  - approval required

- high risk:
  - approval required

## Principles

- approval should be explicit
- operator identity should be recorded
- AI recommendation is not approval
- execution permission is separate from AI output
- AI `requires_approval` is advisory metadata only in Phase 3
- actual approval routing and wait states arrive in a later phase

## Near-term rule

In early phases, prefer stricter approval rather than looser automation.
