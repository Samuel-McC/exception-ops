from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session, sessionmaker

from exception_ops.activities.classification import classify_exception
from exception_ops.activities.remediation import generate_remediation_plan
from exception_ops.config import settings
from exception_ops.db.repositories import (
    create_exception_case,
    get_exception_case,
    get_latest_ai_record,
)
from exception_ops.domain.enums import AIRecordKind, AIRecordStatus, ExceptionType, RiskLevel


def test_ai_activities_persist_outputs_and_complete_workflow(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    session = session_factory()
    try:
        exception_case, _ = create_exception_case(
            session,
            exception_type=ExceptionType.PROVIDER_FAILURE,
            risk_level=RiskLevel.MEDIUM,
            summary="Provider returned 502 during payout processing",
            source_system="payments",
            external_reference="txn-123",
            raw_context_json={"attempt": 1},
        )
    finally:
        session.close()

    asyncio.run(classify_exception(exception_case.case_id))
    remediation_result = asyncio.run(generate_remediation_plan(exception_case.case_id))

    session = session_factory()
    try:
        classification = get_latest_ai_record(session, exception_case.case_id, AIRecordKind.CLASSIFICATION)
        remediation = get_latest_ai_record(session, exception_case.case_id, AIRecordKind.REMEDIATION)
        refreshed_case = get_exception_case(session, exception_case.case_id)
    finally:
        session.close()

    assert classification is not None
    assert classification.status is AIRecordStatus.SUCCEEDED
    assert classification.payload_json is not None
    assert classification.payload_json["normalized_exception_type"] == "provider_failure"

    assert remediation is not None
    assert remediation.status is AIRecordStatus.SUCCEEDED
    assert remediation.payload_json is not None
    assert remediation.payload_json["recommended_action"] == "retry_provider_after_validation"

    assert refreshed_case is not None
    assert refreshed_case.workflow_lifecycle_state.value == "completed"
    assert remediation_result["workflow_lifecycle_state"] == "completed"


def test_ai_activities_record_failures_and_mark_workflow_failed(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    settings.ai_provider = "openai"
    settings.ai_model = "gpt-5.4-mini"
    settings.openai_api_key = ""

    session = session_factory()
    try:
        exception_case, _ = create_exception_case(
            session,
            exception_type=ExceptionType.UNKNOWN,
            risk_level=RiskLevel.HIGH,
            summary="Unknown issue with missing provider credentials",
            source_system="payments",
            external_reference=None,
            raw_context_json={"attempt": 2},
        )
    finally:
        session.close()

    asyncio.run(classify_exception(exception_case.case_id))
    asyncio.run(generate_remediation_plan(exception_case.case_id))

    session = session_factory()
    try:
        classification = get_latest_ai_record(session, exception_case.case_id, AIRecordKind.CLASSIFICATION)
        remediation = get_latest_ai_record(session, exception_case.case_id, AIRecordKind.REMEDIATION)
        refreshed_case = get_exception_case(session, exception_case.case_id)
    finally:
        session.close()

    assert classification is not None
    assert classification.status is AIRecordStatus.FAILED
    assert classification.failure_json is not None

    assert remediation is not None
    assert remediation.status is AIRecordStatus.FAILED
    assert remediation.failure_json is not None

    assert refreshed_case is not None
    assert refreshed_case.workflow_lifecycle_state.value == "failed"
