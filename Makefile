.PHONY: test test-fast replay-fixtures run worker docker-up docker-down

test:
	uv run pytest -q

test-fast:
	uv run pytest -q tests/test_health.py

replay-fixtures:
	uv run python scripts/replay_fixture.py --all

run:
	uv run uvicorn exception_ops.api.app:app --app-dir src --host 127.0.0.1 --port 8000 --reload

worker:
	uv run python -m exception_ops.worker

docker-up:
	docker compose up --build

docker-down:
	docker compose down
