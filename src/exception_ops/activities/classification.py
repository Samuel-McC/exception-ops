from __future__ import annotations

from temporalio import activity


@activity.defn
async def classify_exception(case_id: str) -> dict[str, str]:
    return {
        "case_id": case_id,
        "classification": "unknown",
        "source": "phase0_placeholder",
    }
