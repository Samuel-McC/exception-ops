from __future__ import annotations

from temporalio import workflow


@workflow.defn
class ExceptionResolutionWorkflow:
    @workflow.run
    async def run(self, case_id: str) -> dict[str, str]:
        return {
            "case_id": case_id,
            "status": "phase0_placeholder",
        }
