# Architecture

## System summary

ExceptionOps is an AI-assisted exception-resolution platform built around:
- durable workflow orchestration
- explicit exception state
- bounded LLM assistance
- approval-gated execution
- auditability

The system is intended to ingest operational exceptions, enrich them with evidence, generate structured remediation plans, and execute approved actions through deterministic workflow steps.

## Core invariants

These should not be changed casually:

- Workflow state must remain explicit and inspectable.
- Temporal workflows coordinate long-running process state.
- Activities perform side effects and external calls.
- AI remains advisory unless explicitly approved to act.
- Medium- and high-risk actions require explicit approval.
- Audit records must exist for sensitive decisions and executions.
- Structured outputs are preferred over free-form LLM text.
- Deterministic execution logic remains the final authority.

## Main components

### API surface
FastAPI provides:
- exception ingestion
- exception listing/detail
- explicit approve/reject routes
- minimal server-rendered operator pages for exception review
- operator login/logout
- durable workflow kickoff on create
- health endpoints
- small operator/admin surfaces

### Workflow runtime
Temporal provides:
- durable workflows
- workflow identity per exception case
- recovery from worker restarts
- explicit activity execution boundaries

Current implemented behavior is intentionally small:
- each created exception is assigned a stable Temporal workflow ID
- the API attempts to start the workflow after persisting the case and ingest audit
- workflow linkage is stored back on the exception record
- if Temporal kickoff fails, the case remains persisted with `workflow_lifecycle_state=failed`
- the workflow coordinates evidence collection, classification, remediation, approval gating, and bounded execution through activities
- workflow lifecycle state remains coarse and workflow-level only: `started`, `completed`, or `failed`

### Application state
PostgreSQL stores:
- exception cases
- workflow linkage metadata
- audit records
- additive evidence records with provenance and failure metadata
- additive AI records for classification/remediation outputs and failures
- additive approval decision records
- additive execution records

Schema evolution now runs through Alembic migrations. SQLAlchemy metadata remains the source for model definitions, but Alembic is the authoritative path for evolving existing databases.

### AI layer
The AI layer is bounded and provider-based:
- structured classification
- structured remediation memo generation
- explicit prompt versioning
- provider/model metadata capture
- mock-safe local behavior by default
- later, optional evaluation or confidence/risk guidance

The AI layer does not own execution authority.

### Evidence layer
The evidence layer is also bounded and adapter-based:
- explicit allowlisted evidence adapters only
- mock-safe local behavior by default
- additive evidence records with raw payload, summary, provenance, status, and failure metadata
- no open web search, crawling, or generalized tool calling
- evidence acts as supporting context for AI and operators, not as a replacement for source case truth

### Replay and regression layer
Phase 8 adds a bounded replay layer for V1 hardening:
- a small fixture corpus under `fixtures/v1_cases.json`
- deterministic replay through the current explicit stages
- no extra orchestration runtime beyond the existing activities/adapters
- honest output summaries for approval, AI, evidence, and execution results

Replay is intentionally local/dev oriented:
- it is suitable for regression checks and demos
- it is not a benchmarking platform
- it is not a generalized historical reprocessing engine
- it should not be confused with Temporal workflow history replay

## Planned request / workflow shape

### Ingest
1. caller creates exception
2. exception record is stored
3. ingest audit record is stored
4. workflow kickoff is attempted for the case
5. workflow linkage/state is stored on the exception record

### Workflow
1. accept `case_id`
2. collect bounded evidence through an activity
3. run structured AI classification activity using the source case plus collected evidence
4. run structured AI remediation activity using the source case, collected evidence, and any classification output
5. evaluate deterministic approval policy
6. if approval is not required, mark the case as `approval_state=not_required` and complete the current workflow phase
7. if approval is required, mark the case as `approval_state=pending` and wait for a workflow signal
8. after approve/reject is signaled, mark the case decision state and complete the current workflow phase

Approval semantics stay intentionally split:
- `workflow_lifecycle_state` is coarse and workflow-level only: `started`, `completed`, or `failed`
- `approval_state` represents approval coordination on the case: `pending_policy`, `not_required`, `pending`, `approved`, or `rejected`
- `status` remains a separate case status field and is not overloaded to mean workflow or approval state

Approval persistence is intentionally simple in this phase:
- the API records the approval decision first
- then it signals the workflow with the persisted `decision_id`
- if signaling fails, the persisted decision remains visible and the same action can be retried to reconcile the workflow
- the workflow completes by applying that decision idempotently

Evidence persistence is intentionally additive:
- each collected evidence item becomes its own record
- raw payloads are preserved separately from human-readable summaries
- provenance remains first-class
- evidence collection failures are stored as failed evidence records
- the workflow continues with partial or failed evidence rather than silently dropping the attempt

## Operator auth boundary

Phase 6 adds a minimal, config-backed operator security layer:
- operator credentials and roles are loaded from env or a local file, not from the application database
- session cookies are signed and time-bounded
- operator HTML pages redirect unauthenticated users to login
- protected JSON review/action routes return explicit `auth_required` or `insufficient_role` responses
- CSRF protects login/logout and operator approval forms

The current role model is intentionally small:
- `reviewer`: inspect cases and AI/approval/execution metadata
- `approver`: inspect plus approve/reject
- `executor`: inspect execution-related state; no manual execute route exists yet
- `admin`: full operator access

This is a local/operator boundary, not a full IAM system. SSO/OIDC, password reset, and delegated administration remain later-phase work.

## Persistence evolution

The repo previously relied on a temporary `create_all` bootstrap path. Phase 4.5 introduces Alembic so the intended local/dev path is:
- update models
- create a revision
- review the revision
- run `alembic upgrade head`

The `create_all` path remains available only as an explicit fallback flag for dev/test scenarios and should not be treated as the normal operational path.

Later phases can extend this with broader but still bounded evidence sources, stronger operator lifecycle management, and richer evaluation beyond the current replay corpus.

Phase 8 marks the current repo as a completed V1 foundation. V2 work should extend this base rather than replace it.

## Planned module map

- `src/exception_ops/api/`
  - HTTP routes and app wiring
- `src/exception_ops/workflows/`
  - Temporal workflow definitions
- `src/exception_ops/activities/`
  - deterministic side-effecting work
- `src/exception_ops/ai/`
  - provider abstraction, prompts, structured schemas
- `src/exception_ops/db/`
  - persistence and repositories
- `src/exception_ops/domain/`
  - core enums, models, and services
- `src/exception_ops/config.py`
  - runtime configuration

## Out of scope for early phases

- generalized multi-agent platforming
- autonomous risky action execution
- unconstrained browsing/tool use
- frontend-heavy product work
- speculative infra complexity
