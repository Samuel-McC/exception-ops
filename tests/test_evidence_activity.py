from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session, sessionmaker

from exception_ops.activities.evidence import collect_evidence
from exception_ops.db.repositories import create_exception_case, list_evidence_records
from exception_ops.domain.enums import EvidenceSourceType, EvidenceStatus, ExceptionType, RiskLevel


def test_collect_evidence_persists_bounded_records(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    session = session_factory()
    try:
        exception_case, _ = create_exception_case(
            session,
            exception_type=ExceptionType.PROVIDER_FAILURE,
            risk_level=RiskLevel.MEDIUM,
            summary="Provider timeout returned 502",
            source_system="payments",
            external_reference="txn-123",
            raw_context_json={"attempt": 1, "job_id": "job-123"},
        )
        case_id = exception_case.case_id
    finally:
        session.close()

    result = asyncio.run(collect_evidence(case_id))

    session = session_factory()
    try:
        evidence_history = list_evidence_records(session, case_id)
    finally:
        session.close()

    assert result["items_collected"] == 2
    assert result["items_failed"] == 0
    assert len(evidence_history) == 2
    assert {item.source_type for item in evidence_history} == {
        EvidenceSourceType.CASE_PAYLOAD_SNAPSHOT,
        EvidenceSourceType.PROVIDER_RESPONSE_SNAPSHOT,
    }
    assert all(item.status is EvidenceStatus.SUCCEEDED for item in evidence_history)
    assert all(item.adapter_name == "mock" for item in evidence_history)


def test_collect_evidence_persists_failures_honestly(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    session = session_factory()
    try:
        exception_case, _ = create_exception_case(
            session,
            exception_type=ExceptionType.PROVIDER_FAILURE,
            risk_level=RiskLevel.MEDIUM,
            summary="Provider timeout returned 502",
            source_system="payments",
            external_reference="txn-123",
            raw_context_json={"force_evidence_failure": True},
        )
        case_id = exception_case.case_id
    finally:
        session.close()

    result = asyncio.run(collect_evidence(case_id))

    session = session_factory()
    try:
        evidence_history = list_evidence_records(session, case_id)
    finally:
        session.close()

    assert result["items_collected"] == 0
    assert result["items_failed"] == 1
    assert len(evidence_history) == 1
    assert evidence_history[0].source_type is EvidenceSourceType.COLLECTION_ATTEMPT
    assert evidence_history[0].status is EvidenceStatus.FAILED
    assert evidence_history[0].failure_json is not None
