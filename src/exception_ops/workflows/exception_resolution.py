from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from exception_ops.activities.classification import classify_exception
    from exception_ops.activities.remediation import generate_remediation_plan


@workflow.defn
class ExceptionResolutionWorkflow:
    @workflow.run
    async def run(self, case_id: str) -> dict[str, str]:
        await workflow.execute_activity(
            classify_exception,
            case_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        remediation_result = await workflow.execute_activity(
            generate_remediation_plan,
            case_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return {
            "case_id": case_id,
            "workflow_id": workflow.info().workflow_id,
            "lifecycle_state": remediation_result["workflow_lifecycle_state"],
        }
