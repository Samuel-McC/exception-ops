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
- durable workflow kickoff on create
- health endpoints
- later, small operator/admin surfaces

### Workflow runtime
Temporal provides:
- durable workflows
- workflow identity per exception case
- recovery from worker restarts
- explicit activity execution boundaries

Current Phase 2 behavior is intentionally small:
- each created exception is assigned a stable Temporal workflow ID
- the API attempts to start the workflow after persisting the case and ingest audit
- workflow linkage is stored back on the exception record
- if Temporal kickoff fails, the case remains persisted with `workflow_lifecycle_state=start_failed`

### Application state
PostgreSQL stores:
- exception cases
- workflow linkage metadata
- audit records

### AI layer
The AI layer is bounded and provider-based:
- structured classification
- structured remediation memo generation
- later, optional evaluation or confidence/risk guidance

The AI layer does not own execution authority.

## Planned request / workflow shape

### Ingest
1. caller creates exception
2. exception record is stored
3. ingest audit record is stored
4. workflow kickoff is attempted for the case
5. workflow linkage/state is stored on the exception record

Phase 2 intentionally does not yet:
- wait for approval
- gather real evidence
- classify with AI
- execute actions

### Workflow
1. accept `case_id`
2. return a small replay-safe lifecycle result

Later phases will extend the workflow into classification, evidence gathering, approval gating, and execution.

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
