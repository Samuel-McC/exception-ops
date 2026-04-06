from __future__ import annotations

from temporalio import activity


@activity.defn
async def generate_remediation_plan(case_id: str) -> dict[str, str]:
    return {
        "case_id": case_id,
        "plan": "manual_review",
        "source": "phase0_placeholder",
    }
