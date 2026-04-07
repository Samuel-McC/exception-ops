from __future__ import annotations

from temporalio import workflow


@workflow.defn
class ExceptionResolutionWorkflow:
    @workflow.run
    async def run(self, case_id: str) -> dict[str, str]:
        return {
            "case_id": case_id,
            "workflow_id": workflow.info().workflow_id,
            "lifecycle_state": "started",
        }
