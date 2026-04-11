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
- Temporal workflow kickoff from exception ingest
- stable workflow ID linkage stored on the exception case
- run ID captured when available
- minimal replay-safe workflow definition
- honest workflow failure persistence when Temporal is unavailable

## Phase 3 — AI classification and remediation
- provider abstraction
- structured classification
- structured remediation memo
- additive AI metadata
- structured provider failure records
- workflow-coordinated AI activity execution

## Phase 4 — Approval gate
- approval required for medium/high-risk actions
- explicit approval/reject actions
- additive approval decision records
- workflow wait/signal behavior
- minimal operator UI for review and approval history

## Phase 4.5 — Persistence hardening
- Alembic baseline migration for the current schema
- migration environment and revision workflow
- reduce reliance on startup `create_all`
- honest local/dev migration guidance

## Phase 5 — Execution and audit
- deterministic execution activity
- execution attempt records
- explicit execution state
- bounded execution allowlist and adapter boundary
- richer exception timeline / operator visibility

## Phase 6 — Operator auth and protected actions
- local/operator authentication
- signed session cookies with TTL
- explicit reviewer / approver / executor / admin roles
- CSRF protection on operator form actions
- protected operator UI and sensitive JSON review/action routes

## Phase 7 — Evidence gathering and enrichment
- bounded evidence adapters
- additive evidence records with provenance and honest failure metadata
- workflow evidence stage before AI
- evidence-aware classification and remediation inputs
- operator/detail evidence visibility

## Phase 8 — Evaluation and hardening
- regression fixtures
- deterministic replay through the current explicit stages
- tighter provider/adapter failure inspectability
- local/demo operational polish and clearer V1 guidance

## V1 status

Phases 1 through 8 now form the current V1:
- ingest and durable workflow linkage
- bounded evidence and AI
- human approval gating
- bounded execution
- protected operator UI/actions
- Alembic-backed schema evolution
- deterministic replay fixtures for regression and demos

V2 should build on this base rather than replace it.

Likely V2 directions:
- richer non-mock provider and adapter integrations
- broader but still bounded evaluation/comparison workflows
- stronger deployment and operator lifecycle hardening
- multi-model routing only after V1 baselines remain stable

## Out of scope for now
- multi-agent platforming
- broad RAG platform
- autonomous high-risk action execution
- frontend-heavy buildout
- speculative infra complexity
