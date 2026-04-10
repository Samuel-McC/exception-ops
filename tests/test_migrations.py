from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from exception_ops.api import app as app_module
from exception_ops.config import settings


def test_alembic_upgrade_creates_phase4_schema(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "alembic-phase4.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setattr(settings, "database_url", database_url)

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    table_names = set(inspector.get_table_names())

    assert {
        "alembic_version",
        "exception_cases",
        "audit_events",
        "ai_records",
        "approval_decisions",
    }.issubset(table_names)

    exception_case_columns = {column["name"] for column in inspector.get_columns("exception_cases")}
    assert {
        "case_id",
        "exception_type",
        "status",
        "risk_level",
        "temporal_workflow_id",
        "workflow_lifecycle_state",
        "approval_state",
        "created_at",
        "updated_at",
    }.issubset(exception_case_columns)


def test_app_startup_skips_create_all_when_db_auto_create_disabled(monkeypatch) -> None:
    calls: list[bool] = []

    monkeypatch.setattr(settings, "db_auto_create", False)
    monkeypatch.setattr(app_module, "init_db", lambda: calls.append(True))

    with TestClient(app_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert calls == []


def test_app_startup_allows_explicit_dev_create_all_fallback(monkeypatch) -> None:
    calls: list[bool] = []

    monkeypatch.setattr(settings, "db_auto_create", True)
    monkeypatch.setattr(app_module, "init_db", lambda: calls.append(True))

    with TestClient(app_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert calls == [True]
