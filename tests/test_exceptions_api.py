from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from exception_ops.activities.approval import evaluate_approval_gate
from exception_ops.activities.classification import classify_exception
from exception_ops.activities.evidence import collect_evidence
from exception_ops.activities.execution import execute_action
from exception_ops.activities.remediation import generate_remediation_plan
from tests.conftest import StubWorkflowSignaler, StubWorkflowStarter, login_as


def _build_payload(
    summary: str,
    source_system: str,
    *,
    risk_level: str = "medium",
    external_reference: str | None = None,
) -> dict:
    return {
        "exception_type": "provider_failure",
        "risk_level": risk_level,
        "summary": summary,
        "source_system": source_system,
        "external_reference": external_reference,
        "raw_context_json": {"job_id": "job-123", "attempt": 1},
    }


def _prepare_pending_approval_case(case_id: str) -> None:
    asyncio.run(collect_evidence(case_id))
    asyncio.run(classify_exception(case_id))
    asyncio.run(generate_remediation_plan(case_id))
    asyncio.run(evaluate_approval_gate(case_id))


def _prepare_executed_low_risk_case(case_id: str) -> None:
    asyncio.run(collect_evidence(case_id))
    asyncio.run(classify_exception(case_id))
    asyncio.run(generate_remediation_plan(case_id))
    asyncio.run(evaluate_approval_gate(case_id))
    asyncio.run(execute_action(case_id))


def test_create_exception(client: TestClient, workflow_starter: StubWorkflowStarter) -> None:
    response = client.post("/exceptions", json=_build_payload("Provider returned 502", "payments"))

    assert response.status_code == 201
    body = response.json()
    assert body["case_id"]
    assert body["exception_type"] == "provider_failure"
    assert body["status"] == "ingested"
    assert body["risk_level"] == "medium"
    assert body["summary"] == "Provider returned 502"
    assert body["source_system"] == "payments"
    assert body["raw_context_json"] == {"job_id": "job-123", "attempt": 1}
    assert len(body["audit_history"]) == 1
    assert body["temporal_workflow_id"] == f"exception-resolution-{body['case_id']}"
    assert body["temporal_run_id"] == f"run-{body['case_id']}"
    assert body["workflow_lifecycle_state"] == "started"
    assert body["approval_state"] == "pending_policy"
    assert body["approval_required"] is None
    assert body["execution_state"] == "pending"
    assert body["latest_classification"] is None
    assert body["latest_remediation"] is None
    assert body["latest_approval_decision"] is None
    assert body["latest_execution"] is None
    assert workflow_starter.started_workflows == [(body["case_id"], body["temporal_workflow_id"])]


def test_list_exceptions_returns_newest_first(client: TestClient) -> None:
    first = client.post("/exceptions", json=_build_payload("First exception", "payments")).json()
    second = client.post("/exceptions", json=_build_payload("Second exception", "ledger")).json()
    login_as(client, "reviewer")

    response = client.get("/exceptions")

    assert response.status_code == 200
    body = response.json()
    assert [item["case_id"] for item in body["items"]] == [second["case_id"], first["case_id"]]
    assert body["items"][0]["temporal_workflow_id"] == second["temporal_workflow_id"]
    assert body["items"][0]["workflow_lifecycle_state"] == "started"
    assert body["items"][0]["approval_state"] == "pending_policy"
    assert body["items"][0]["execution_state"] == "pending"


def test_get_exception_by_id_returns_case_audit_and_approval_metadata(client: TestClient) -> None:
    created = client.post(
        "/exceptions",
        json=_build_payload("Missing statement", "documents", external_reference="doc-99"),
    ).json()
    login_as(client, "reviewer")

    response = client.get(f"/exceptions/{created['case_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == created["case_id"]
    assert body["external_reference"] == "doc-99"
    assert body["audit_history"][0]["event_type"] == "ingested"
    assert body["temporal_workflow_id"] == created["temporal_workflow_id"]
    assert body["temporal_run_id"] == created["temporal_run_id"]
    assert body["workflow_lifecycle_state"] == "started"
    assert body["approval_state"] == "pending_policy"
    assert body["execution_state"] == "pending"
    assert body["approval_history"] == []
    assert body["execution_history"] == []


def test_ingest_creates_audit_record(client: TestClient) -> None:
    created = client.post(
        "/exceptions",
        json=_build_payload("Payout mismatch", "reconciliation", external_reference="txn-42"),
    ).json()
    login_as(client, "reviewer")

    detail = client.get(f"/exceptions/{created['case_id']}")

    assert detail.status_code == 200
    audit_history = detail.json()["audit_history"]
    assert len(audit_history) == 1
    assert audit_history[0]["actor"] == "system:api"
    assert audit_history[0]["payload_json"] == {
        "exception_type": "provider_failure",
        "source_system": "reconciliation",
        "external_reference": "txn-42",
    }


def test_workflow_start_failure_returns_created_case_with_failed_lifecycle(
    client: TestClient,
    workflow_starter: StubWorkflowStarter,
) -> None:
    workflow_starter.should_fail = True

    response = client.post("/exceptions", json=_build_payload("Temporal offline", "payments"))

    assert response.status_code == 201
    body = response.json()
    assert body["case_id"]
    assert body["temporal_workflow_id"] == f"exception-resolution-{body['case_id']}"
    assert body["temporal_run_id"] is None
    assert body["workflow_lifecycle_state"] == "failed"
    assert body["approval_state"] == "pending_policy"
    assert body["execution_state"] == "pending"
    assert len(body["audit_history"]) == 1

    login_as(client, "reviewer")
    detail = client.get(f"/exceptions/{body['case_id']}")
    assert detail.status_code == 200
    assert detail.json()["workflow_lifecycle_state"] == "failed"


def test_get_exception_detail_returns_ai_and_pending_approval_metadata(
    client: TestClient,
    activity_db_overrides: None,
) -> None:
    created = client.post("/exceptions", json=_build_payload("Provider timeout 502", "payments")).json()

    _prepare_pending_approval_case(created["case_id"])
    login_as(client, "reviewer")

    response = client.get(f"/exceptions/{created['case_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_lifecycle_state"] == "started"
    assert body["approval_state"] == "pending"
    assert body["approval_required"] is True
    assert body["execution_state"] == "pending"
    assert len(body["evidence_history"]) >= 2
    assert body["evidence_history"][0]["adapter_name"] == "mock"
    assert body["latest_classification"]["status"] == "succeeded"
    assert body["latest_classification"]["provider"] == "mock"
    assert body["latest_classification"]["route"]["path_name"] == "triage"
    assert body["latest_classification"]["usage"]["total_tokens"] is not None
    assert body["latest_classification"]["trace"]["model_path"] == "triage"
    assert body["latest_classification"]["output"]["normalized_exception_type"] == "provider_failure"
    assert body["latest_remediation"]["status"] == "succeeded"
    assert body["latest_remediation"]["route"]["path_name"] == "planner_default"
    assert body["latest_remediation"]["usage"]["total_tokens"] is not None
    assert body["latest_remediation"]["trace"]["model_path"] == "planner_default"
    assert body["latest_remediation"]["output"]["recommended_action"] == "retry_provider_after_validation"
    assert body["latest_remediation"]["output"]["requires_approval"] is True
    assert body["ai_trace"]["triage"]["model_path"] == "triage"
    assert body["ai_trace"]["planning"]["model_path"] == "planner_default"
    assert body["ai_trace"]["fallback_occurred"] is False
    assert body["latest_approval_decision"] is None
    assert body["latest_execution"] is None


def test_get_exception_detail_returns_execution_metadata_after_low_risk_execution(
    client: TestClient,
    activity_db_overrides: None,
) -> None:
    created = client.post(
        "/exceptions",
        json=_build_payload("Provider timeout 502", "payments", risk_level="low"),
    ).json()

    _prepare_executed_low_risk_case(created["case_id"])
    login_as(client, "reviewer")

    response = client.get(f"/exceptions/{created['case_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["approval_state"] == "not_required"
    assert body["execution_state"] == "succeeded"
    assert body["workflow_lifecycle_state"] == "completed"
    assert body["latest_execution"]["status"] == "succeeded"
    assert body["latest_execution"]["action_name"] == "retry_provider_after_validation"
    assert len(body["execution_history"]) == 1


def test_approve_route_records_decision_and_signals_workflow(
    client: TestClient,
    workflow_signaler: StubWorkflowSignaler,
    activity_db_overrides: None,
) -> None:
    created = client.post("/exceptions", json=_build_payload("Provider timeout 502", "payments")).json()
    _prepare_pending_approval_case(created["case_id"])
    login_as(client, "approver")

    response = client.post(
        f"/exceptions/{created['case_id']}/approve",
        json={"reason": "Verified the provider retry plan."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approval_state"] == "approved"
    assert body["workflow_lifecycle_state"] == "started"
    assert body["latest_approval_decision"]["decision"] == "approved"
    assert body["latest_approval_decision"]["actor"] == "approver"
    assert len(body["approval_history"]) == 1
    assert workflow_signaler.signaled_workflows == [
        (created["temporal_workflow_id"], body["latest_approval_decision"]["decision_id"])
    ]


def test_reject_route_records_decision_and_signals_workflow(
    client: TestClient,
    workflow_signaler: StubWorkflowSignaler,
    activity_db_overrides: None,
) -> None:
    created = client.post("/exceptions", json=_build_payload("Provider timeout 502", "payments")).json()
    _prepare_pending_approval_case(created["case_id"])
    login_as(client, "approver")

    response = client.post(
        f"/exceptions/{created['case_id']}/reject",
        json={"reason": "Need manual investigation before any action."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approval_state"] == "rejected"
    assert body["latest_approval_decision"]["decision"] == "rejected"
    assert body["latest_approval_decision"]["actor"] == "approver"
    assert len(body["approval_history"]) == 1
    assert workflow_signaler.signaled_workflows == [
        (created["temporal_workflow_id"], body["latest_approval_decision"]["decision_id"])
    ]


def test_approve_route_allows_retry_when_signal_failed(
    client: TestClient,
    workflow_signaler: StubWorkflowSignaler,
    activity_db_overrides: None,
) -> None:
    created = client.post("/exceptions", json=_build_payload("Provider timeout 502", "payments")).json()
    _prepare_pending_approval_case(created["case_id"])
    login_as(client, "approver")
    workflow_signaler.should_fail = True

    first = client.post(
        f"/exceptions/{created['case_id']}/approve",
        json={"reason": "Initial approval attempt."},
    )

    assert first.status_code == 502
    client.cookies.clear()
    login_as(client, "reviewer")
    detail = client.get(f"/exceptions/{created['case_id']}").json()
    decision_id = detail["latest_approval_decision"]["decision_id"]
    assert detail["approval_state"] == "approved"
    assert detail["workflow_lifecycle_state"] == "started"

    client.cookies.clear()
    login_as(client, "approver")
    workflow_signaler.should_fail = False
    second = client.post(
        f"/exceptions/{created['case_id']}/approve",
        json={},
    )

    assert second.status_code == 200
    second_body = second.json()
    assert second_body["latest_approval_decision"]["decision_id"] == decision_id
    assert workflow_signaler.signaled_workflows[-1] == (created["temporal_workflow_id"], decision_id)


def test_invalid_state_approval_attempt_fails_cleanly(
    client: TestClient,
    activity_db_overrides: None,
) -> None:
    created = client.post(
        "/exceptions",
        json=_build_payload("Low risk document issue", "documents", risk_level="low"),
    ).json()
    asyncio.run(classify_exception(created["case_id"]))
    asyncio.run(generate_remediation_plan(created["case_id"]))
    asyncio.run(evaluate_approval_gate(created["case_id"]))
    login_as(client, "approver")

    response = client.post(
        f"/exceptions/{created['case_id']}/approve",
        json={"reason": "Should not be needed."},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Exception case is not waiting for approval"


def test_get_exception_returns_404_for_missing_case(client: TestClient) -> None:
    login_as(client, "reviewer")
    response = client.get("/exceptions/missing-case")

    assert response.status_code == 404
    assert response.json()["detail"] == "Exception case not found"


def test_get_exception_detail_returns_failed_evidence_history_when_collection_fails(
    client: TestClient,
    activity_db_overrides: None,
) -> None:
    created = client.post(
        "/exceptions",
        json={
            **_build_payload("Provider timeout 502", "payments"),
            "raw_context_json": {"force_evidence_failure": True},
        },
    ).json()

    asyncio.run(collect_evidence(created["case_id"]))
    asyncio.run(classify_exception(created["case_id"]))
    asyncio.run(generate_remediation_plan(created["case_id"]))
    login_as(client, "reviewer")

    response = client.get(f"/exceptions/{created['case_id']}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["evidence_history"]) == 1
    assert body["evidence_history"][0]["status"] == "failed"
    assert body["evidence_history"][0]["source_type"] == "collection_attempt"
    assert body["evidence_history"][0]["failure_json"]["type"] == "RuntimeError"
