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
- approval wait/signal behavior
- retry/failure behavior

### API tests
- ingest
- list/detail
- approval endpoints
- execution endpoints

### Integration tests
- DB-backed flows
- Temporal worker/workflow path
- mocked AI provider path

## Testing rule

Focused tests first, full suite second.

## Regression-sensitive areas
- workflow determinism
- approval semantics
- AI structured output parsing
- execution retry behavior
- audit record completeness
