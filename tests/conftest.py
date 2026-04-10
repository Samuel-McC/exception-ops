from __future__ import annotations

import json
import re
from collections.abc import Generator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from exception_ops.activities import approval as approval_activity
from exception_ops.activities import classification as classification_activity
from exception_ops.activities import execution as execution_activity
from exception_ops.activities import remediation as remediation_activity
from exception_ops.api.app import app
from exception_ops.auth import hash_password
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

TEST_OPERATOR_PASSWORDS = {
    "reviewer": "reviewer-password",
    "approver": "approver-password",
    "executor": "executor-password",
    "admin": "admin-password",
}
TEST_OPERATOR_CONFIG = {
    "reviewer": {
        "password_hash": hash_password(
            TEST_OPERATOR_PASSWORDS["reviewer"],
            salt=b"reviewer-salt-01",
        ),
        "roles": ["reviewer"],
    },
    "approver": {
        "password_hash": hash_password(
            TEST_OPERATOR_PASSWORDS["approver"],
            salt=b"approver-salt-01",
        ),
        "roles": ["reviewer", "approver"],
    },
    "executor": {
        "password_hash": hash_password(
            TEST_OPERATOR_PASSWORDS["executor"],
            salt=b"executor-salt-01",
        ),
        "roles": ["reviewer", "executor"],
    },
    "admin": {
        "password_hash": hash_password(
            TEST_OPERATOR_PASSWORDS["admin"],
            salt=b"admin-user-salt1",
        ),
        "roles": ["admin"],
    },
}


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
        "execution_adapter": settings.execution_adapter,
        "operator_session_secret": settings.operator_session_secret,
        "operator_session_ttl_seconds": settings.operator_session_ttl_seconds,
        "operator_secure_cookies": settings.operator_secure_cookies,
        "operator_users_json": settings.operator_users_json,
        "operator_users_file": settings.operator_users_file,
    }
    settings.ai_enabled = True
    settings.ai_provider = "mock"
    settings.ai_model = "mock-heuristic-v1"
    settings.openai_api_key = ""
    settings.execution_adapter = "mock"
    settings.operator_session_secret = "test-session-secret"
    settings.operator_session_ttl_seconds = 3600
    settings.operator_secure_cookies = False
    settings.operator_users_json = json.dumps(TEST_OPERATOR_CONFIG)
    settings.operator_users_file = ""
    try:
        yield
    finally:
        settings.ai_enabled = original["ai_enabled"]
        settings.ai_provider = original["ai_provider"]
        settings.ai_model = original["ai_model"]
        settings.openai_api_key = original["openai_api_key"]
        settings.execution_adapter = original["execution_adapter"]
        settings.operator_session_secret = original["operator_session_secret"]
        settings.operator_session_ttl_seconds = original["operator_session_ttl_seconds"]
        settings.operator_secure_cookies = original["operator_secure_cookies"]
        settings.operator_users_json = original["operator_users_json"]
        settings.operator_users_file = original["operator_users_file"]


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
    monkeypatch.setattr(execution_activity, "get_session_factory", lambda: session_factory)
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


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if match is None:
        raise AssertionError("csrf_token input not found in HTML")
    return match.group(1)


def login_as(
    client: TestClient,
    username: str,
    *,
    password: str | None = None,
    next_path: str = "/operator/exceptions",
) -> None:
    login_page = client.get(f"/operator/login?next={next_path}")
    assert login_page.status_code == 200
    csrf_token = extract_csrf_token(login_page.text)
    response = client.post(
        "/operator/login",
        data={
            "username": username,
            "password": password or TEST_OPERATOR_PASSWORDS[username],
            "csrf_token": csrf_token,
            "next": next_path,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
