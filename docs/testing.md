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
- later, approval wait/signal behavior

### API tests
- ingest
- list/detail
- workflow kickoff linkage
- honest kickoff-failure behavior

### Integration tests
- DB-backed flows
- Temporal worker/workflow path
- mocked AI provider path

## Testing rule

Focused tests first, full suite second.

## Regression-sensitive areas
- workflow determinism
- workflow kickoff persistence
- audit record completeness
