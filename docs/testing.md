# Testing

## Testing goals

ExceptionOps should prioritize:
- workflow correctness
- explicit state transitions
- evidence persistence and provenance
- AI output contract validation
- approval-gate behavior
- auth/authz and CSRF boundaries
- activity failure handling
- audit/event correctness

## Expected test layers

### Unit tests
- domain logic
- evidence adapter behavior
- AI provider formatting/parsing
- approval policy
- repositories/helpers

### Workflow tests
- workflow state progression
- evidence collection before AI steps
- retry/failure behavior
- approval wait/signal behavior

### API tests
- ingest
- list/detail
- workflow kickoff linkage
- honest kickoff-failure behavior
- detail visibility for collected evidence
- detail visibility for latest AI records
- approve/reject route behavior
- auth-required and insufficient-role behavior on protected JSON routes
- honest approval-signal failure behavior

### Integration tests
- DB-backed flows
- Temporal worker/workflow path
- evidence persistence and honest failure capture
- mocked AI provider path
- minimal operator UI coverage through server-rendered responses
- login/logout and CSRF-protected operator form coverage
- Alembic upgrade wiring and startup gating checks

### Replay / regression tests
- fixture-corpus validation for the bounded V1 replay set
- deterministic replay through the explicit stage order
- expectation matching for approval, evidence, AI, and execution outcomes
- provider/adapter failure fixtures that stay honest about bounded failure paths

## Testing rule

Focused tests first, full suite second.

## Regression-sensitive areas
- workflow determinism
- workflow kickoff persistence
- evidence persistence, provenance visibility, and failure capture
- AI record persistence and failure capture
- approval decision persistence and retry/reconciliation behavior
- authenticated operator identity on approval decisions
- signed session / CSRF protection on operator actions
- replay fixture expectations and deterministic stage ordering
- normalized evidence/execution failure metadata
- migration baseline accuracy versus current SQLAlchemy metadata
- audit record completeness
