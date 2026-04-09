# Operations

## Local development goals

Local development should support:
- API startup
- DB-backed exception persistence
- Temporal workflow kickoff and worker execution
- bounded AI classification/remediation with a safe local provider path
- explicit approval gating and operator review
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
- `POST /exceptions` persists the case and then attempts Temporal kickoff
- `POST /exceptions/{case_id}/approve` and `POST /exceptions/{case_id}/reject` record operator decisions and signal the workflow
- `GET /operator/exceptions` and `GET /operator/exceptions/{case_id}` provide a minimal server-rendered operator UI

### Run worker
- start Temporal worker for workflows and activities
- current workflow runs bounded classification/remediation activities and stays replay-safe

### Run tests
- focused pytest slices
- full pytest suite

### Health
- `/health`

### Workflow linkage visibility
- `GET /exceptions`
- `GET /exceptions/{case_id}`

These endpoints expose:
- `temporal_workflow_id`
- `temporal_run_id`
- `workflow_lifecycle_state`
- `approval_state`
- latest approval decision and approval history on detail
- latest classification/remediation AI metadata when available

If Temporal is unavailable at create time, the case still exists and `workflow_lifecycle_state` is stored as `failed`.

If approval signaling fails after a decision is recorded, the API returns an honest error and the case still shows the persisted approval decision. Retry the same approve/reject action to reconcile the workflow signal path.

### AI provider modes
- `AI_PROVIDER=mock` is the safe local default
- `AI_PROVIDER=openai` is opt-in and requires `OPENAI_API_KEY`

If AI generation fails, the exception case remains available and the failure is stored as an additive AI record.

## Operational principles

- workflows should be replay-safe
- activities should own side effects
- AI should remain additive and bounded
- approval and execution should always be inspectable
- approval does not trigger execution yet in this phase
