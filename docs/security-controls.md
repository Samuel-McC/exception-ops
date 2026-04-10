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
- bounded evidence adapter layer with a mock-safe local default
- additive evidence records with provenance and honest failure metadata
- audit-style persistence for AI successes and failures
- deterministic activity boundaries for external calls
- explicit human approval state on exception cases
- additive approval decision records before workflow signaling
- workflow wait/signal semantics instead of ad hoc approval polling
- explicit execution state on exception cases
- additive execution records with request/result/failure payloads
- bounded execution adapter allowlist with a mock-safe default
- config-backed operator authentication
- signed operator session cookies with TTL
- explicit role checks on protected review/action routes
- CSRF protection on login/logout and operator form actions
- authenticated operator identity bound to persisted approval decisions

## Planned controls

### Authentication and authorization
- SSO/OIDC or federated identity
- delegated admin and richer operator lifecycle management
- password reset / credential rotation flows
- stronger admin separation for future execution/admin actions

### Secrets handling
- API keys from environment variables
- no secrets committed to source control
- provider credentials separated by environment

### AI safety and control
- structured outputs
- provider abstraction
- bounded prompts
- bounded evidence context
- additive persistence of AI outputs
- AI failure visibility without hidden fallback execution
- no autonomous risky execution
- explicit approval for risky actions
- AI approval hints remain advisory only
- AI recommended actions remain advisory only

### Evidence safety and control
- allowlisted evidence adapters only
- no open web search or generalized crawling
- provenance remains visible with each evidence record
- raw evidence is preserved separately from summaries
- evidence failures are stored explicitly

### Workflow / execution safety
- durable workflow history
- retries around activities
- deterministic workflow logic
- isolated execution activities
- audit trail for approvals and actions

## Honest current limitation

Phase 6 adds a real operator boundary, but it remains intentionally small:
- credentials are config-backed rather than database-backed
- there is no SSO/OIDC yet
- there is no password reset or delegated admin flow yet
- deployment hardening still depends on environment-specific ingress, TLS, and secret management outside the app
- evidence gathering is bounded and adapter-backed, not a generalized research or agent system

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
