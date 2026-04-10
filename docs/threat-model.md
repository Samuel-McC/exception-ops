# Threat Model

This document captures the main trust boundaries, assets, and expected threats for ExceptionOps.

## Primary assets

- exception cases
- additive evidence records
- remediation plans
- additive AI records
- additive execution records
- audit records
- AI provider credentials
- operator identity and actions

## Trust boundaries

1. external caller -> API ingress
2. operator -> operator/admin routes
3. application -> PostgreSQL
4. application/worker -> Temporal
5. activities -> external systems/tools/providers
6. AI provider integration -> OpenAI or later providers

## Main threats

### Unauthorized execution
Risk:
- a user or service triggers remediation without appropriate approval

Mitigation direction:
- explicit approval gates
- authenticated operator actions
- signed operator sessions
- explicit role checks on sensitive review/action routes
- CSRF protection on browser form actions
- role-based authorization
- audit trail
- bounded execution allowlist

### AI overreach
Risk:
- model output is treated as authoritative
- AI recommends or triggers unsafe action without control

Mitigation direction:
- AI is advisory only
- structured output contracts
- provider/model/prompt metadata are persisted with each AI record
- AI failures are stored explicitly instead of hidden behind fallback execution
- deterministic execution path
- explicit approval for risky actions
- approval policy is deterministic and based on case risk, not AI authority

### Tool-side effect misuse
Risk:
- activity calls a real external system incorrectly
- retries accidentally amplify effects

Mitigation direction:
- activities are explicit
- retries are controlled
- execution attempts are recorded
- execution adapters are bounded and explicit
- later, idempotency keys where relevant

### Incomplete evidence or bad classification
Risk:
- remediation plan is based on poor evidence
- misclassification leads to bad operator decisions

Mitigation direction:
- bounded evidence adapters with visible provenance
- additive evidence records with honest failure capture
- bounded taxonomy and structured classification schema
- clear separation between source exception fields and additive AI records
- clear separation between source case input and additive evidence
- clear operator visibility
- confidence/risk fields are exposed in structured AI output
- approval decisions are stored separately from AI suggestions
- evaluation and test fixtures later

### Evidence provenance drift
Risk:
- supporting context is collected without clear source attribution
- operators cannot tell raw evidence from summaries or failed collection attempts

Mitigation direction:
- each evidence record stores source type, source name, adapter name, collected time, and provenance metadata
- raw evidence payloads are preserved separately from summaries
- failed evidence attempts are stored explicitly
- detail views expose evidence provenance directly

### Approval signaling drift
Risk:
- an approval decision is recorded but the workflow signal does not reach Temporal

Mitigation direction:
- persist the approval decision before signaling
- keep workflow and approval state separate on the case
- return an honest error so the same action can be retried for reconciliation
- keep workflow-side application of the stored decision idempotent

### Secret exposure
Risk:
- API keys leak through source, logs, or debug output

Mitigation direction:
- environment variables only
- sanitized examples
- careful logging boundaries

## Residual risk at early stage

At early stages, the main residual risks are:
- local-only auth model without SSO/OIDC
- no password reset or delegated admin lifecycle yet
- weak deployment defaults
- immature evaluation of AI outputs
- evidence sources are still bounded and mock/local-safe rather than broad production integrations
- execution side effects are still mock/local-safe rather than real production integrations
