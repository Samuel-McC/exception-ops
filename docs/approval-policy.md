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
- approval or rejection completes the approval-gating phase

## Phase 5 execution interaction

- approved and `not_required` cases now continue automatically into bounded execution
- rejected cases terminate without execution
- execution still passes through deterministic execution policy and an allowlisted action mapping
- AI output does not approve, reject, or directly execute on behalf of an operator

## Phase 6 operator authority

- approval and rejection now require an authenticated operator session
- approval actors are taken from the authenticated session identity, not caller-supplied request data
- `approver` and `admin` roles can approve/reject
- `reviewer` can inspect approval state and AI metadata but cannot make decisions
- this is still a local/config-backed auth model, not full enterprise IAM

## Near-term rule

In early phases, prefer stricter approval rather than looser automation.
