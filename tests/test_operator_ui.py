from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from exception_ops.activities.approval import evaluate_approval_gate
from exception_ops.activities.classification import classify_exception
from exception_ops.activities.remediation import generate_remediation_plan


def _build_payload(summary: str, *, risk_level: str = "medium") -> dict:
    return {
        "exception_type": "provider_failure",
        "risk_level": risk_level,
        "summary": summary,
        "source_system": "payments",
        "external_reference": "txn-123",
        "raw_context_json": {"job_id": "job-123", "attempt": 1},
    }


def _prepare_pending_approval_case(case_id: str) -> None:
    asyncio.run(classify_exception(case_id))
    asyncio.run(generate_remediation_plan(case_id))
    asyncio.run(evaluate_approval_gate(case_id))


def test_operator_exceptions_list_renders_cases(client: TestClient) -> None:
    client.post("/exceptions", json=_build_payload("First exception"))
    client.post("/exceptions", json=_build_payload("Second exception"))

    response = client.get("/operator/exceptions")

    assert response.status_code == 200
    assert "ExceptionOps Operator View" in response.text
    assert "First exception" in response.text
    assert "Second exception" in response.text
    assert "/operator/exceptions/" in response.text


def test_operator_exception_detail_renders_ai_and_approval_controls(
    client: TestClient,
    activity_db_overrides: None,
) -> None:
    created = client.post("/exceptions", json=_build_payload("Provider timeout")).json()
    _prepare_pending_approval_case(created["case_id"])

    response = client.get(f"/operator/exceptions/{created['case_id']}")

    assert response.status_code == 200
    assert "Approval State" in response.text
    assert "pending" in response.text
    assert "retry_provider_after_validation" in response.text
    assert f'/operator/exceptions/{created["case_id"]}/approve' in response.text
    assert f'/operator/exceptions/{created["case_id"]}/reject' in response.text


def test_operator_approve_redirects_back_to_detail_with_message(
    client: TestClient,
    activity_db_overrides: None,
) -> None:
    created = client.post("/exceptions", json=_build_payload("Provider timeout")).json()
    _prepare_pending_approval_case(created["case_id"])

    response = client.post(
        f"/operator/exceptions/{created['case_id']}/approve",
        data={"actor": "operator:alice", "reason": "Looks safe to continue."},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/operator/exceptions/{created['case_id']}?message=Case%20approved."

    redirected = client.get(response.headers["location"])
    assert redirected.status_code == 200
    assert "Case approved." in redirected.text
    assert "approved" in redirected.text
