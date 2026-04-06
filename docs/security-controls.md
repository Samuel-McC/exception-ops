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

At the earliest setup stage, implemented controls may be minimal.
As the project grows, this document should be updated.

Expected near-term implemented controls:
- explicit workflow state instead of hidden side effects
- bounded AI provider abstraction
- approval gating for risky actions
- environment-based secret loading
- audit records for sensitive actions
- deterministic activity boundaries for external calls

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
- no autonomous risky execution
- explicit approval for risky actions

### Workflow / execution safety
- durable workflow history
- retries around activities
- deterministic workflow logic
- isolated execution activities
- audit trail for approvals and actions

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
