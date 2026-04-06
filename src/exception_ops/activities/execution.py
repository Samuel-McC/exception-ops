from __future__ import annotations

from temporalio import activity


@activity.defn
async def execute_action(case_id: str) -> dict[str, str]:
    return {
        "case_id": case_id,
        "execution": "not_implemented",
        "source": "phase0_placeholder",
    }
