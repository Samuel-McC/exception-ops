from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from exception_ops.api.app import app
from exception_ops.db import Base, get_session
from exception_ops.db import models as db_models  # noqa: F401
from exception_ops.temporal import WorkflowStartError, WorkflowStartResult, get_workflow_starter


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
def client(
    session_factory: sessionmaker[Session],
    workflow_starter: StubWorkflowStarter,
) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_workflow_starter] = lambda: workflow_starter

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
