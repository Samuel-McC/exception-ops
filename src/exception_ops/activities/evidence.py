from __future__ import annotations

from temporalio import activity


@activity.defn
async def collect_evidence(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "evidence_items": [],
        "source": "phase0_placeholder",
    }
