# Operations

## Local development goals

Local development should support:
- API startup
- DB-backed exception persistence
- explicit DB migrations
- Temporal workflow kickoff and worker execution
- bounded AI classification/remediation with a safe local provider path
- explicit approval gating and operator review
- bounded execution with a safe local adapter path
- local/operator authentication for protected review/action routes
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
- migrate first with `alembic upgrade head`
- `POST /exceptions` persists the case and then attempts Temporal kickoff
- `POST /exceptions/{case_id}/approve` and `POST /exceptions/{case_id}/reject` record operator decisions and signal the workflow
- `GET /operator/exceptions` and `GET /operator/exceptions/{case_id}` provide a minimal server-rendered operator UI
- execution runs automatically in the workflow after `approved` or `not_required`
- `GET /operator/login` and `POST /operator/logout` provide the minimal operator auth flow

### Run worker
- start Temporal worker for workflows and activities
- run after the database has been migrated with Alembic
- current workflow runs bounded classification/remediation activities and stays replay-safe

### Run migrations
- create a blank revision:
  - `alembic revision -m "describe change"`
- autogenerate from metadata:
  - `alembic revision --autogenerate -m "describe change"`
- upgrade to latest:
  - `alembic upgrade head`

For Docker-based local work, a simple pattern is:
- `docker compose run --rm app alembic upgrade head`
- `docker compose up app worker`

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
- `execution_state`
- latest approval decision and approval history on detail
- latest classification/remediation AI metadata when available
- latest execution record and execution history on detail

Phase 6 route boundary:
- public:
  - `/health`
  - `POST /exceptions`
- protected HTML:
  - `/operator/exceptions`
  - `/operator/exceptions/{case_id}`
  - operator approve/reject form posts
- protected JSON:
  - `GET /exceptions`
  - `GET /exceptions/{case_id}`
  - `POST /exceptions/{case_id}/approve`
  - `POST /exceptions/{case_id}/reject`

If Temporal is unavailable at create time, the case still exists and `workflow_lifecycle_state` is stored as `failed`.

If approval signaling fails after a decision is recorded, the API returns an honest error and the case still shows the persisted approval decision. Retry the same approve/reject action to reconcile the workflow signal path.

### Schema management
- Alembic is the authoritative schema evolution path
- `DB_AUTO_CREATE` is disabled by default and should only be used as an explicit temporary dev/test fallback
- older local databases created through earlier bootstrap flows may still need a reset before adopting Alembic cleanly

### AI provider modes
- `AI_PROVIDER=mock` is the safe local default
- `AI_PROVIDER=openai` is opt-in and requires `OPENAI_API_KEY`

### Execution adapter modes
- `EXECUTION_ADAPTER=mock` is the safe local default
- execution remains bounded to allowlisted actions only

### Operator auth config
- set `OPERATOR_SESSION_SECRET`
- keep `OPERATOR_SECURE_COOKIES=false` only for local HTTP dev; enable it for HTTPS environments
- configure operators through `OPERATOR_USERS_JSON` or `OPERATOR_USERS_FILE`
- `.env.example` includes a local admin example for development only
- operator sessions are cookie-based and time-bounded
- operator form actions require CSRF tokens

Current auth limitations:
- local/config-backed credentials only
- no SSO/OIDC
- no password reset
- no delegated admin or broader operator lifecycle tooling

If AI generation fails, the exception case remains available and the failure is stored as an additive AI record.

If execution fails, the failure is stored as an additive execution record and the case remains visible with `execution_state=failed`.

## Operational principles

- workflows should be replay-safe
- activities should own side effects
- AI should remain additive and bounded
- approval and execution should always be inspectable
- AI remains advisory while execution stays bounded and explicit
