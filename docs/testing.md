# Testing

## Testing goals

ExceptionOps should prioritize:
- workflow correctness
- explicit state transitions
- AI output contract validation
- approval-gate behavior
- activity failure handling
- audit/event correctness

## Expected test layers

### Unit tests
- domain logic
- AI provider formatting/parsing
- approval policy
- repositories/helpers

### Workflow tests
- workflow state progression
- retry/failure behavior
- approval wait/signal behavior

### API tests
- ingest
- list/detail
- workflow kickoff linkage
- honest kickoff-failure behavior
- detail visibility for latest AI records
- approve/reject route behavior
- honest approval-signal failure behavior

### Integration tests
- DB-backed flows
- Temporal worker/workflow path
- mocked AI provider path
- minimal operator UI coverage through server-rendered responses
- Alembic upgrade wiring and startup gating checks

## Testing rule

Focused tests first, full suite second.

## Regression-sensitive areas
- workflow determinism
- workflow kickoff persistence
- AI record persistence and failure capture
- approval decision persistence and retry/reconciliation behavior
- migration baseline accuracy versus current SQLAlchemy metadata
- audit record completeness
