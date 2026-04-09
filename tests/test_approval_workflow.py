from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest
from sqlalchemy.orm import Session, sessionmaker
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from exception_ops.activities.approval import evaluate_approval_gate, finalize_approval_decision
from exception_ops.activities.classification import classify_exception
from exception_ops.activities.execution import execute_action
from exception_ops.activities.remediation import generate_remediation_plan
from exception_ops.db.repositories import (
    create_approval_decision,
    create_exception_case,
    get_exception_case,
    get_latest_execution_record,
    update_exception_case_workflow,
)
from exception_ops.domain.enums import (
    ApprovalDecisionType,
    ApprovalState,
    ExecutionState,
    ExceptionType,
    RiskLevel,
)
from exception_ops.temporal import build_exception_workflow_id
from exception_ops.workflows.exception_resolution import ExceptionResolutionWorkflow


async def _wait_for_approval_state(
    session_factory: sessionmaker[Session],
    case_id: str,
    approval_state: ApprovalState,
) -> None:
    for _ in range(40):
        session = session_factory()
        try:
            exception_case = get_exception_case(session, case_id)
        finally:
            session.close()
        if exception_case is not None and exception_case.approval_state is approval_state:
            return
        await asyncio.sleep(0.1)

    raise AssertionError(f"Timed out waiting for {case_id} to reach approval state {approval_state}")


@pytest.mark.asyncio
async def test_workflow_waits_for_approval_and_completes_on_signal(
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
        workflow_id = build_exception_workflow_id(exception_case.case_id)
        update_exception_case_workflow(
            session,
            case_id=exception_case.case_id,
            temporal_workflow_id=workflow_id,
            temporal_run_id=None,
            workflow_lifecycle_state=exception_case.workflow_lifecycle_state,
        )
    finally:
        session.close()

    async with await WorkflowEnvironment.start_time_skipping() as env:
        worker = Worker(
            env.client,
            task_queue="test-approval-task-queue",
            workflows=[ExceptionResolutionWorkflow],
            activities=[
                classify_exception,
                generate_remediation_plan,
                evaluate_approval_gate,
                finalize_approval_decision,
                execute_action,
            ],
        )
        worker_task = asyncio.create_task(worker.run())
        try:
            handle = await env.client.start_workflow(
                ExceptionResolutionWorkflow.run,
                exception_case.case_id,
                id=workflow_id,
                task_queue="test-approval-task-queue",
            )

            await _wait_for_approval_state(
                session_factory,
                exception_case.case_id,
                ApprovalState.PENDING,
            )

            session = session_factory()
            try:
                refreshed_case = get_exception_case(session, exception_case.case_id)
                assert refreshed_case is not None
                assert refreshed_case.approval_state is ApprovalState.PENDING
                assert refreshed_case.workflow_lifecycle_state.value == "started"

                refreshed_case, decision = create_approval_decision(
                    session,
                    case_id=exception_case.case_id,
                    decision=ApprovalDecisionType.APPROVED,
                    actor="operator:alice",
                    reason="Verified the remediation plan.",
                )
            finally:
                session.close()

            await handle.signal(
                ExceptionResolutionWorkflow.submit_approval_decision,
                decision.decision_id,
            )
            result = await handle.result()
        finally:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task

    session = session_factory()
    try:
        final_case = get_exception_case(session, exception_case.case_id)
        latest_execution = get_latest_execution_record(session, exception_case.case_id)
    finally:
        session.close()

    assert result["approval_state"] == "approved"
    assert result["execution_state"] == "succeeded"
    assert result["lifecycle_state"] == "completed"
    assert final_case is not None
    assert final_case.approval_state is ApprovalState.APPROVED
    assert final_case.execution_state is ExecutionState.SUCCEEDED
    assert final_case.workflow_lifecycle_state.value == "completed"
    assert latest_execution is not None
    assert latest_execution.action_name.value == "retry_provider_after_validation"
