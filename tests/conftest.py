from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from exception_ops.activities import approval as approval_activity
from exception_ops.activities import classification as classification_activity
from exception_ops.activities import remediation as remediation_activity
from exception_ops.api.app import app
from exception_ops.config import settings
from exception_ops.db import Base, get_session
from exception_ops.db import models as db_models  # noqa: F401
from exception_ops.temporal import (
    WorkflowSignalError,
    WorkflowStartError,
    WorkflowStartResult,
    get_workflow_signaler,
    get_workflow_starter,
)


@dataclass
class StubWorkflowStarter:
    should_fail: bool = False
    started_workflows: list[tuple[str, str]] = field(default_factory=list)

    async def start_exception_workflow(self, case_id: str, workflow_id: str) -> WorkflowStartResult:
        self.started_workflows.append((case_id, workflow_id))
        if self.should_fail:
            raise WorkflowStartError(workflow_id)

        return WorkflowStartResult(
            workflow_id=workflow_id,
            run_id=f"run-{case_id}",
        )


@dataclass
class StubWorkflowSignaler:
    should_fail: bool = False
    signaled_workflows: list[tuple[str, str]] = field(default_factory=list)

    async def signal_approval_decision(self, workflow_id: str, decision_id: str) -> None:
        self.signaled_workflows.append((workflow_id, decision_id))
        if self.should_fail:
            raise WorkflowSignalError(workflow_id)


@pytest.fixture(autouse=True)
def reset_ai_settings() -> Generator[None, None, None]:
    original = {
        "ai_enabled": settings.ai_enabled,
        "ai_provider": settings.ai_provider,
        "ai_model": settings.ai_model,
        "openai_api_key": settings.openai_api_key,
    }
    settings.ai_enabled = True
    settings.ai_provider = "mock"
    settings.ai_model = "mock-heuristic-v1"
    settings.openai_api_key = ""
    try:
        yield
    finally:
        settings.ai_enabled = original["ai_enabled"]
        settings.ai_provider = original["ai_provider"]
        settings.ai_model = original["ai_model"]
        settings.openai_api_key = original["openai_api_key"]


@pytest.fixture()
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def workflow_starter() -> StubWorkflowStarter:
    return StubWorkflowStarter()


@pytest.fixture()
def workflow_signaler() -> StubWorkflowSignaler:
    return StubWorkflowSignaler()


@pytest.fixture()
def activity_db_overrides(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:
    monkeypatch.setattr(approval_activity, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(classification_activity, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(remediation_activity, "get_session_factory", lambda: session_factory)


@pytest.fixture()
def client(
    session_factory: sessionmaker[Session],
    workflow_starter: StubWorkflowStarter,
    workflow_signaler: StubWorkflowSignaler,
) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_workflow_starter] = lambda: workflow_starter
    app.dependency_overrides[get_workflow_signaler] = lambda: workflow_signaler

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
