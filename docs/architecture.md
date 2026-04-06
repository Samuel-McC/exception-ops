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
- approval/rejection actions
- execution triggers
- health endpoints
- later, small operator/admin surfaces

### Workflow runtime
Temporal provides:
- durable workflows
- waiting states
- approval pauses
- retries
- recovery from worker restarts
- explicit activity execution boundaries

### Application state
PostgreSQL stores:
- exception cases
- evidence records
- remediation plans
- approval decisions
- execution attempts
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
3. workflow is started for the case

### Workflow
1. classify exception
2. gather evidence
3. generate remediation plan
4. determine whether approval is required
5. if approval required, wait
6. if approved, execute safe deterministic action
7. record final state and audit trail

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
