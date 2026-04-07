from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import StubWorkflowStarter


def _build_payload(summary: str, source_system: str, external_reference: str | None = None) -> dict:
    return {
        "exception_type": "provider_failure",
        "risk_level": "medium",
        "summary": summary,
        "source_system": source_system,
        "external_reference": external_reference,
        "raw_context_json": {"job_id": "job-123", "attempt": 1},
    }


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
    assert workflow_starter.started_workflows == [(body["case_id"], body["temporal_workflow_id"])]


def test_list_exceptions_returns_newest_first(client: TestClient) -> None:
    first = client.post("/exceptions", json=_build_payload("First exception", "payments")).json()
    second = client.post("/exceptions", json=_build_payload("Second exception", "ledger")).json()

    response = client.get("/exceptions")

    assert response.status_code == 200
    body = response.json()
    assert [item["case_id"] for item in body["items"]] == [second["case_id"], first["case_id"]]
    assert body["items"][0]["temporal_workflow_id"] == second["temporal_workflow_id"]
    assert body["items"][0]["workflow_lifecycle_state"] == "started"


def test_get_exception_by_id_returns_case_and_audit_history(client: TestClient) -> None:
    created = client.post(
        "/exceptions",
        json=_build_payload("Missing statement", "documents", external_reference="doc-99"),
    ).json()

    response = client.get(f"/exceptions/{created['case_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == created["case_id"]
    assert body["external_reference"] == "doc-99"
    assert body["audit_history"][0]["event_type"] == "ingested"
    assert body["temporal_workflow_id"] == created["temporal_workflow_id"]
    assert body["temporal_run_id"] == created["temporal_run_id"]
    assert body["workflow_lifecycle_state"] == "started"


def test_ingest_creates_audit_record(client: TestClient) -> None:
    created = client.post(
        "/exceptions",
        json=_build_payload("Payout mismatch", "reconciliation", external_reference="txn-42"),
    ).json()

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
    assert body["workflow_lifecycle_state"] == "start_failed"
    assert len(body["audit_history"]) == 1

    detail = client.get(f"/exceptions/{body['case_id']}")
    assert detail.status_code == 200
    assert detail.json()["workflow_lifecycle_state"] == "start_failed"


def test_get_exception_returns_404_for_missing_case(client: TestClient) -> None:
    response = client.get("/exceptions/missing-case")

    assert response.status_code == 404
    assert response.json()["detail"] == "Exception case not found"
