# Operations

## Local development goals

Local development should support:
- API startup
- DB-backed exception persistence
- explicit DB migrations
- Temporal workflow kickoff and worker execution
- bounded evidence collection with a safe local adapter path
- bounded AI classification/remediation with a safe local provider path
- bounded AI routing between triage and planning paths
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
- the workflow now collects bounded evidence before classification/remediation
- `POST /exceptions/{case_id}/approve` and `POST /exceptions/{case_id}/reject` record operator decisions and signal the workflow
- `GET /operator/exceptions` and `GET /operator/exceptions/{case_id}` provide a minimal server-rendered operator UI
- execution runs automatically in the workflow after `approved` or `not_required`
- `GET /operator/login` and `POST /operator/logout` provide the minimal operator auth flow

### Run worker
- start Temporal worker for workflows and activities
- run after the database has been migrated with Alembic
- current workflow runs bounded evidence collection, classification, remediation, approval gating, and execution activities
- workflow logic stays replay-safe because side effects remain inside activities

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
- Ruff after tests

### Replay fixtures
- replay the full deterministic V1 fixture corpus:
  - `make replay-fixtures`
- replay one fixture:
  - `uv run python scripts/replay_fixture.py --fixture-id approval-required-provider-failure`
- stop after a selected stage:
  - `uv run python scripts/replay_fixture.py --fixture-id approval-required-provider-failure --until-stage approval_gate`

Replay is intentionally bounded:
- it creates a new case and reuses the current explicit stages in-process
- it does not start Temporal workflows
- it is meant for local regression/demo work, not production reprocessing or benchmarking

### Seeded demo path
- run `alembic upgrade head`
- start the API with `make run`
- seed representative cases with `make replay-fixtures`
- log in to `/operator/login` with the local operator credentials from `.env.example`
- inspect approval, evidence, AI, and execution history through the operator UI

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
- collected evidence history with provenance and honest failure metadata on detail
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
- stable V1-compatible path:
  - `AI_PROVIDER=mock`
  - `AI_MODEL=mock-heuristic-v1`
- V2 Phase 1 task-specific overrides are optional:
  - `AI_TRIAGE_PROVIDER`
  - `AI_TRIAGE_MODEL`
  - `AI_PLANNER_PROVIDER`
  - `AI_PLANNER_MODEL`
  - `AI_PLANNER_ESCALATION_PROVIDER`
  - `AI_PLANNER_ESCALATION_MODEL`
  - `AI_FALLBACK_PROVIDER`
  - `AI_FALLBACK_MODEL`
  - `AI_TRIAGE_CONFIDENCE_THRESHOLD`
- `AI_PROVIDER=openai` remains opt-in and requires `OPENAI_API_KEY`
- if task-specific settings are unset, the app stays on the V1-compatible global provider/model path

### Evidence adapter modes
- `EVIDENCE_ADAPTER=mock` is the safe local default
- evidence remains bounded to allowlisted adapters only
- this phase does not include open web search, crawling, or generalized research agents

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

If AI routing requests a stronger planning path, that escalation is stored on the corresponding AI record. If provider fallback is configured and used, the fallback attempt is also stored on the AI record instead of being hidden behind fake success.

If evidence collection fails, the exception case remains available and the failure is stored as an additive evidence record. The workflow continues with whatever evidence is available instead of silently dropping the attempt.

If execution fails, the failure is stored as an additive execution record and the case remains visible with `execution_state=failed`.

If an evidence or execution adapter fails, the stored failure metadata now includes the adapter name and stage so replay output and operator detail stay inspectable without guessing where the failure occurred.

## Operational principles

- workflows should be replay-safe
- activities should own side effects
- evidence should remain bounded, additive, and provenance-first
- AI should remain additive and bounded
- AI routing should remain explicit, task-bounded, and inspectable
- approval and execution should always be inspectable
- AI remains advisory while execution stays bounded and explicit
