# Operations

## Local development goals

Local development should support:
- API startup
- DB-backed exception persistence
- Temporal workflow execution
- AI provider configuration
- deterministic testing

## Expected local stack

- FastAPI app
- PostgreSQL
- Temporal
- Temporal UI
- local environment config via `.env`

## Planned common commands

### Run app
- start FastAPI dev server

### Run worker
- start Temporal worker for workflows and activities

### Run tests
- focused pytest slices
- full pytest suite

### Health
- `/health`

## Operational principles

- workflows should be replay-safe
- activities should own side effects
- AI should remain additive and bounded
- approval and execution should always be inspectable
