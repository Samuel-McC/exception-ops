from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session, sessionmaker

from exception_ops.activities.approval import evaluate_approval_gate, finalize_approval_decision
from exception_ops.activities.classification import classify_exception
from exception_ops.activities.execution import execute_action
from exception_ops.activities.remediation import generate_remediation_plan
from exception_ops.db.repositories import (
    create_approval_decision,
    create_exception_case,
    get_exception_case,
    get_latest_execution_record,
)
from exception_ops.domain.enums import (
    ApprovalDecisionType,
    ApprovalState,
    ExecutionState,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)


def test_execution_runs_for_approved_cases(
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
            external_reference="txn-777",
            raw_context_json={"attempt": 1},
        )
        case_id = exception_case.case_id
    finally:
        session.close()

    asyncio.run(classify_exception(case_id))
    asyncio.run(generate_remediation_plan(case_id))
    asyncio.run(evaluate_approval_gate(case_id))

    session = session_factory()
    try:
        _, decision = create_approval_decision(
            session,
            case_id=case_id,
            decision=ApprovalDecisionType.APPROVED,
            actor="operator:alice",
            reason="Approved for bounded retry.",
        )
    finally:
        session.close()

    asyncio.run(finalize_approval_decision(decision.decision_id))
    execution_result = asyncio.run(execute_action(case_id))

    session = session_factory()
    try:
        refreshed_case = get_exception_case(session, case_id)
        execution_record = get_latest_execution_record(session, case_id)
    finally:
        session.close()

    assert execution_result["execution_state"] == "succeeded"
    assert refreshed_case is not None
    assert refreshed_case.approval_state is ApprovalState.APPROVED
    assert refreshed_case.execution_state is ExecutionState.SUCCEEDED
    assert refreshed_case.workflow_lifecycle_state is WorkflowLifecycleState.COMPLETED
    assert execution_record is not None
    assert execution_record.action_name.value == "retry_provider_after_validation"
    assert execution_record.status.value == "succeeded"


def test_execution_failure_is_persisted_honestly(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    session = session_factory()
    try:
        exception_case, _ = create_exception_case(
            session,
            exception_type=ExceptionType.PROVIDER_FAILURE,
            risk_level=RiskLevel.LOW,
            summary="Provider timeout returned 502",
            source_system="payments",
            external_reference="txn-888",
            raw_context_json={"attempt": 1, "force_execution_failure": True},
        )
        case_id = exception_case.case_id
    finally:
        session.close()

    asyncio.run(classify_exception(case_id))
    asyncio.run(generate_remediation_plan(case_id))
    asyncio.run(evaluate_approval_gate(case_id))
    execution_result = asyncio.run(execute_action(case_id))

    session = session_factory()
    try:
        refreshed_case = get_exception_case(session, case_id)
        execution_record = get_latest_execution_record(session, case_id)
    finally:
        session.close()

    assert execution_result["execution_state"] == "failed"
    assert refreshed_case is not None
    assert refreshed_case.approval_state is ApprovalState.NOT_REQUIRED
    assert refreshed_case.execution_state is ExecutionState.FAILED
    assert refreshed_case.workflow_lifecycle_state is WorkflowLifecycleState.FAILED
    assert execution_record is not None
    assert execution_record.status.value == "failed"
    assert execution_record.failure_payload_json is not None


def test_rejected_cases_do_not_execute(
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
            external_reference="txn-999",
            raw_context_json={"attempt": 1},
        )
        case_id = exception_case.case_id
    finally:
        session.close()

    asyncio.run(classify_exception(case_id))
    asyncio.run(generate_remediation_plan(case_id))
    asyncio.run(evaluate_approval_gate(case_id))

    session = session_factory()
    try:
        _, decision = create_approval_decision(
            session,
            case_id=case_id,
            decision=ApprovalDecisionType.REJECTED,
            actor="operator:bob",
            reason="Rejected the proposed action.",
        )
    finally:
        session.close()

    asyncio.run(finalize_approval_decision(decision.decision_id))
    execution_result = asyncio.run(execute_action(case_id))

    session = session_factory()
    try:
        refreshed_case = get_exception_case(session, case_id)
        execution_record = get_latest_execution_record(session, case_id)
    finally:
        session.close()

    assert execution_result["execution_state"] == "skipped"
    assert refreshed_case is not None
    assert refreshed_case.approval_state is ApprovalState.REJECTED
    assert refreshed_case.execution_state is ExecutionState.SKIPPED
    assert refreshed_case.workflow_lifecycle_state is WorkflowLifecycleState.COMPLETED
    assert execution_record is None
