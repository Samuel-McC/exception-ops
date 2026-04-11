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
2. gather bounded evidence
3. classify exception
4. generate remediation plan
5. require approval for risky actions
6. execute approved actions
7. audit everything

## Current status

Stable tagged baseline:
- V1.0.0 is the completed V1 foundation that shipped:
- Phase 1 exception ingestion with persistence and ingest audit records
- Phase 2 Temporal workflow kickoff on exception creation
- stored workflow linkage on each exception case
- Phase 3 bounded AI classification and remediation records coordinated through workflow activities
- additive AI persistence with structured outputs, provider/model metadata, and honest failure records
- Phase 4 explicit approval gating with persisted approval decisions, workflow wait/signal behavior, and a minimal server-rendered operator UI
- Phase 4.5 Alembic-based schema migrations for the current persistence model
- Phase 5 bounded execution with additive execution records, explicit execution state, and a mock-safe adapter allowlist
- Phase 6 local/operator authentication with signed session cookies, role-based authorization, and CSRF-protected operator form actions
- Phase 7 bounded evidence collection with additive evidence records, provenance metadata, and evidence-aware AI inputs
- Phase 8 replay fixtures, deterministic stage replay, and V1 hardening around provider/adapter failure visibility

This V2 branch now adds Phase 1 multi-step AI orchestration:
- explicit classifier/triage path and planner/remediation path split
- dedicated routing policy for bounded task/model selection
- confidence-aware planning escalation
- optional provider fallback visibility
- additive routing, usage, cost, and compact trace metadata on `ai_records`
- operator/detail visibility into which path handled triage/planning and why

When `POST /exceptions` succeeds, the exception case and ingest audit record are always persisted first. The API then attempts workflow kickoff and stores one of:
- `started`
- `failed`

This keeps exception ingestion durable even if Temporal is temporarily unavailable.

The safe local default remains `AI_PROVIDER=mock`, which preserves the V1-compatible single global provider/model path unless you opt into task-specific overrides. The OpenAI path remains opt-in and bounded to structured outputs only.

The safe local default is also `EVIDENCE_ADAPTER=mock`, which collects bounded, explicit evidence records such as:
- source case payload snapshots
- related provider or document snapshots
- internal reference lookups
- prior execution snapshots when available

Evidence is additive:
- raw evidence payloads are preserved
- summaries, provenance, and failures are stored separately
- evidence does not overwrite source case input
- evidence failures are persisted honestly instead of silently disappearing

Medium- and high-risk cases now move into an explicit approval flow. Approval decisions are persisted before workflow signaling so the operator action remains auditable even if Temporal signaling fails; if that happens, the API and operator UI return an honest error and the same approve/reject action can be retried to reconcile the workflow.

Execution remains bounded and explicit:
- low-risk or approved cases can continue into allowlisted execution through the workflow
- rejected cases stop without execution
- execution remains deterministic and auditable
- AI remains advisory only and does not approve or execute on its own

Phase 7 places evidence before AI in the workflow:
- the workflow collects bounded evidence first
- classification and remediation use evidence as additional structured context
- source case fields remain the source truth
- evidence failures do not block reads and do not turn the system into an agentic research workflow

Phase 8 closes out the current V1 surface with:
- a small regression fixture corpus under `fixtures/v1_cases.json`
- deterministic local replay through the existing explicit stages and adapters
- normalized evidence/execution failure metadata for clearer operator and replay inspection
- clearer demo and operational guidance for local runs

V2 Phase 1 keeps the same workflow order but extends the AI seam:
- triage/classification and planning/remediation now have explicit task-specific prompt versions
- routing stays bounded to inspectable task/complexity rules in code
- fallback and escalation are visible in persisted metadata rather than hidden in helper behavior
- usage/cost metadata is best-effort and honest, not fake precision
- the operator UI shows a compact routing trace instead of pseudo-reasoning text

Phase 6 adds a real operator boundary around the review/approval surface:
- `/health` stays public
- `POST /exceptions` stays public/internal for ingestion
- `/operator/*` pages require login and redirect unauthenticated users to `/operator/login`
- sensitive JSON review/action routes require authentication and explicit roles
- operator sessions are cookie-based and signed
- operator form actions use CSRF tokens

This is still a local/config-backed auth model. It does not yet include SSO/OIDC, password reset, delegated admin, or broader enterprise IAM behavior.

## V1 replay and demo path

The simplest local/demo path is now:

1. run `alembic upgrade head`
2. start the API with `make run`
3. optionally start the worker with `make worker` if you want to drive cases through live Temporal kickoff
4. seed deterministic sample cases with `make replay-fixtures`
5. sign in to `/operator/login` with the local operator credentials from `.env.example`

Replay stays intentionally bounded:
- it reuses the existing explicit stages in order: evidence, classification, remediation, approval gate, optional approval decision, execution
- it uses the same bounded adapters/providers that the app already uses
- it is a local/dev regression and demo tool, not a benchmarking platform or autonomous orchestration layer

Useful replay commands:
- replay the full fixture corpus:
  - `make replay-fixtures`
- replay one fixture:
  - `uv run python scripts/replay_fixture.py --fixture-id approval-required-provider-failure`
- stop after a selected stage:
  - `uv run python scripts/replay_fixture.py --fixture-id approval-required-provider-failure --until-stage approval_gate`

V1 is meant to be a stable, believable demo system:
- durable ingestion and workflow linkage
- bounded evidence, AI, approval, and execution
- protected operator review/actions
- additive records and honest failure persistence

It is still not production-ready:
- mock adapters remain the default for local safety
- auth is local/config-backed rather than enterprise IAM
- replay is fixture/sample-case based rather than a general evaluation platform
- broader production integrations, generalized agents, and eval-platform behavior are still deferred to later V2 phases

## V2 Phase 1 AI orchestration

The current V2 Phase 1 additions are intentionally narrow:
- `classification.v3.triage` handles bounded triage on the configured triage path
- `remediation.v3.plan` handles bounded planning on the configured planner path
- routing can request a stronger planning path when signals such as low triage confidence, unknown type, incomplete evidence, or higher risk make that worthwhile
- provider fallback is optional and visible when configured
- `AI_PROVIDER` / `AI_MODEL` still provide a clean V1-compatible default path when task-specific settings are unset

What this does not add:
- generalized agents
- open-ended tool use
- workflow redesign
- critique/review loops
- broad evaluation platforming

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
- evidence remains bounded, explicit, and provenance-first
- AI must not autonomously approve or execute risky actions
- AI outputs are additive records, not silent overwrites of the source exception
- approvals remain explicit
- approval does not silently bypass execution policy
- auditability is a first-class requirement
- each phase should stay small and testable
