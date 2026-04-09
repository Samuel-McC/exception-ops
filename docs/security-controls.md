# Security Controls

This document describes the intended security posture of ExceptionOps.

It should be kept honest and split between:
- implemented today
- planned later

## Current posture

At this setup stage, the repo should be treated as:
- development-first
- internal/operator-oriented
- not production-ready
- not internet-exposed by default

## Implemented today

Current implemented controls are still development-oriented, but they include:
- explicit workflow state instead of hidden side effects
- bounded AI provider abstraction
- structured outputs only for AI generation
- prompt version capture on persisted AI records
- provider/model metadata capture on persisted AI records
- environment-based secret loading
- mock-safe local AI default without external credentials
- audit-style persistence for AI successes and failures
- deterministic activity boundaries for external calls
- explicit human approval state on exception cases
- additive approval decision records before workflow signaling
- workflow wait/signal semantics instead of ad hoc approval polling
- explicit execution state on exception cases
- additive execution records with request/result/failure payloads
- bounded execution adapter allowlist with a mock-safe default

## Planned controls

### Authentication and authorization
- authenticated operator access
- role-based approval permissions
- restricted execution/admin actions
- explicit session/operator identity for sensitive decisions

### Secrets handling
- API keys from environment variables
- no secrets committed to source control
- provider credentials separated by environment

### AI safety and control
- structured outputs
- provider abstraction
- bounded prompts
- additive persistence of AI outputs
- AI failure visibility without hidden fallback execution
- no autonomous risky execution
- explicit approval for risky actions
- AI approval hints remain advisory only
- AI recommended actions remain advisory only

### Workflow / execution safety
- durable workflow history
- retries around activities
- deterministic workflow logic
- isolated execution activities
- audit trail for approvals and actions

## Honest current limitation

Phase 5 approval and execution are explicit, but they are not yet access-controlled. The approve/reject routes, operator UI, and execution path should still be treated as development/internal surfaces until auth/authz lands in a later phase.

### Platform hardening
- dockerized local environment
- constrained service boundaries
- deployment-time ingress hardening later
- dependency scanning and CI later

## Honest boundary

ExceptionOps should be described as:
- workflow-first
- approval-gated
- AI-bounded
- security-aware

It should not be described as:
- production hardened
- enterprise-ready
- fully compliant
- autonomous
