# ExceptionOps

ExceptionOps is an AI-assisted exception-resolution platform.

It ingests operational exceptions, gathers evidence through deterministic activities, uses bounded LLM assistance to classify issues and draft remediation plans, routes risky actions to explicit approval, and executes approved actions through durable workflows.

## Why this exists

Most AI demos stop at “the model answered.”

This project focuses on the harder engineering problems around AI automation:

- durable workflow orchestration
- explicit exception state transitions
- structured AI outputs
- bounded tool use
- approval-gated execution
- auditability
- failure handling and retries
- clear separation between AI recommendation and deterministic execution

The goal is to build a production-minded automation system, not a generic chatbot or unconstrained agent demo.

## Planned stack

- Python
- FastAPI
- Temporal
- PostgreSQL
- OpenAI
- Pydantic
- Docker
- Pytest

## Planned core flow

1. ingest exception
2. classify exception
3. gather evidence
4. generate remediation plan
5. require approval for risky actions
6. execute approved actions
7. audit everything

## Current status

This repo currently implements:
- Phase 1 exception ingestion with persistence and ingest audit records
- Phase 2 Temporal workflow kickoff on exception creation
- stored workflow linkage on each exception case
- Phase 3 bounded AI classification and remediation records coordinated through workflow activities
- additive AI persistence with structured outputs, provider/model metadata, and honest failure records
- Phase 4 explicit approval gating with persisted approval decisions, workflow wait/signal behavior, and a minimal server-rendered operator UI
- Phase 4.5 Alembic-based schema migrations for the current persistence model
- Phase 5 bounded execution with additive execution records, explicit execution state, and a mock-safe adapter allowlist
- Phase 6 local/operator authentication with signed session cookies, role-based authorization, and CSRF-protected operator form actions

When `POST /exceptions` succeeds, the exception case and ingest audit record are always persisted first. The API then attempts workflow kickoff and stores one of:
- `started`
- `failed`

This keeps exception ingestion durable even if Temporal is temporarily unavailable.

The safe local default is `AI_PROVIDER=mock`, which produces structured classification and remediation output without requiring external credentials. The OpenAI path is opt-in and remains bounded to structured outputs only.

Medium- and high-risk cases now move into an explicit approval flow. Approval decisions are persisted before workflow signaling so the operator action remains auditable even if Temporal signaling fails; if that happens, the API and operator UI return an honest error and the same approve/reject action can be retried to reconcile the workflow.

Execution remains bounded and explicit:
- low-risk or approved cases can continue into allowlisted execution through the workflow
- rejected cases stop without execution
- execution remains deterministic and auditable
- AI remains advisory only and does not approve or execute on its own

Phase 6 adds a real operator boundary around the review/approval surface:
- `/health` stays public
- `POST /exceptions` stays public/internal for ingestion
- `/operator/*` pages require login and redirect unauthenticated users to `/operator/login`
- sensitive JSON review/action routes require authentication and explicit roles
- operator sessions are cookie-based and signed
- operator form actions use CSRF tokens

This is still a local/config-backed auth model. It does not yet include SSO/OIDC, password reset, delegated admin, or broader enterprise IAM behavior.

## Database migrations

Alembic is now the authoritative schema evolution path for local/dev databases. The temporary `DB_AUTO_CREATE` path still exists, but it is disabled by default and should only be used as a narrow dev/test fallback.

Common commands:

- create a revision:
  - `alembic revision -m "describe change"`
- autogenerate from SQLAlchemy metadata when appropriate:
  - `alembic revision --autogenerate -m "describe change"`
- upgrade the database:
  - `alembic upgrade head`
- run the app against a migrated database:
  - first run `alembic upgrade head`
  - then start the app/worker normally

Honest limitation:
- older local databases that were created through earlier ad hoc `create_all` flows may still need a reset before adopting Alembic cleanly
- after this phase, new schema changes should go through Alembic revisions rather than bootstrap shortcuts

## Design principles

- workflows first, not agent sprawl
- deterministic execution remains authoritative
- AI can classify, summarize, and recommend
- AI must not autonomously approve or execute risky actions
- AI outputs are additive records, not silent overwrites of the source exception
- approvals remain explicit
- approval does not silently bypass execution policy
- auditability is a first-class requirement
- each phase should stay small and testable
