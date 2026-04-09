from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from exception_ops.activities.approval import (
        evaluate_approval_gate,
        finalize_approval_decision,
    )
    from exception_ops.activities.classification import classify_exception
    from exception_ops.activities.execution import execute_action
    from exception_ops.activities.remediation import generate_remediation_plan


@workflow.defn
class ExceptionResolutionWorkflow:
    def __init__(self) -> None:
        self._approval_decision_id: str | None = None

    @workflow.signal
    def submit_approval_decision(self, decision_id: str) -> None:
        self._approval_decision_id = decision_id

    @workflow.run
    async def run(self, case_id: str) -> dict[str, str]:
        await workflow.execute_activity(
            classify_exception,
            case_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.execute_activity(
            generate_remediation_plan,
            case_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        approval_result = await workflow.execute_activity(
            evaluate_approval_gate,
            case_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        if approval_result["requires_approval"]:
            await workflow.wait_condition(lambda: self._approval_decision_id is not None)
            approval_result = await workflow.execute_activity(
                finalize_approval_decision,
                self._approval_decision_id,
                start_to_close_timeout=timedelta(seconds=30),
            )
        execution_result = await workflow.execute_activity(
            execute_action,
            case_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        return {
            "case_id": case_id,
            "workflow_id": workflow.info().workflow_id,
            "approval_state": approval_result["approval_state"],
            "execution_state": execution_result["execution_state"],
            "lifecycle_state": execution_result["workflow_lifecycle_state"],
        }
