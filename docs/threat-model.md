# Threat Model

This document captures the main trust boundaries, assets, and expected threats for ExceptionOps.

## Primary assets

- exception cases
- approval decisions
- remediation plans
- evidence gathered from tools or external systems
- execution attempts
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
- role-based authorization
- audit trail

### AI overreach
Risk:
- model output is treated as authoritative
- AI recommends or triggers unsafe action without control

Mitigation direction:
- AI is advisory only
- structured output contracts
- deterministic execution path
- explicit approval for risky actions

### Tool-side effect misuse
Risk:
- activity calls a real external system incorrectly
- retries accidentally amplify effects

Mitigation direction:
- activities are explicit
- retries are controlled
- execution attempts are recorded
- later, idempotency keys where relevant

### Incomplete evidence or bad classification
Risk:
- remediation plan is based on poor evidence
- misclassification leads to bad operator decisions

Mitigation direction:
- explicit evidence stage
- clear operator visibility
- confidence/risk fields later
- evaluation and test fixtures later

### Secret exposure
Risk:
- API keys leak through source, logs, or debug output

Mitigation direction:
- environment variables only
- sanitized examples
- careful logging boundaries

## Residual risk at early stage

At early stages, the main residual risks are:
- incomplete auth/authz
- insufficient operator controls
- weak deployment defaults
- immature evaluation of AI outputs


