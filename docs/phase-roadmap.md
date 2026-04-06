# Phase Roadmap

## Goal

Build ExceptionOps as a production-minded AI-assisted exception-resolution system.

## Phase 0 — Base setup
- repo scaffold
- config
- docs
- health endpoint
- workflow/runtime boundaries defined

## Phase 1 — Exception ingestion
- exception model
- create/list/detail endpoints
- persistence
- audit event on ingest

## Phase 2 — Durable workflow
- Temporal workflow
- worker bootstrap
- explicit status progression
- deterministic activity boundaries

## Phase 3 — AI classification and remediation
- provider abstraction
- structured classification
- structured remediation memo
- additive AI metadata

## Phase 4 — Approval gate
- approval required for medium/high-risk actions
- explicit approval/reject actions
- workflow wait/signal behavior

## Phase 5 — Execution and audit
- deterministic execution activity
- execution attempt records
- exception timeline / operator visibility

## Phase 6 — Evaluation and hardening
- regression fixtures
- provider failure behavior
- stronger security/authz
- replay and operational polish

## Out of scope for now
- multi-agent platforming
- broad RAG platform
- autonomous high-risk action execution
- frontend-heavy buildout
- speculative infra complexity
