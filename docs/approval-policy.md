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
- AI `requires_approval` and `execution_risk` are advisory metadata only
- actual approval routing and wait states are implemented in Phase 4

## Implemented in Phase 4

- medium- and high-risk cases require approval
- low-risk cases do not require approval in this phase
- the case stores an explicit `approval_state`
- approval decisions are stored as additive records with actor, reason, and timestamp
- the workflow waits for approval by signal when approval is required
- approval or rejection completes the current non-executing workflow phase

## What approval does not do yet

- approval does not trigger execution
- approval does not override deterministic execution safeguards that will land later
- AI output does not approve or reject on behalf of an operator

## Near-term rule

In early phases, prefer stricter approval rather than looser automation.
