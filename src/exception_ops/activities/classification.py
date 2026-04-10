from __future__ import annotations

from temporalio import activity

from exception_ops.ai.service import get_ai_service
from exception_ops.db import get_session_factory
from exception_ops.db.repositories import create_ai_record, get_exception_case, list_evidence_records
from exception_ops.domain.enums import AIRecordKind


@activity.defn
async def classify_exception(case_id: str) -> dict[str, str]:
    session = get_session_factory()()
    try:
        exception_case = get_exception_case(session, case_id)
        if exception_case is None:
            raise ValueError(f"Exception case not found: {case_id}")

        evidence_records = list(reversed(list_evidence_records(session, case_id)))
        result = await get_ai_service().classify_exception(exception_case, evidence_records)
        create_ai_record(
            session,
            case_id=case_id,
            record_kind=AIRecordKind.CLASSIFICATION,
            status=result.status,
            provider=result.provider,
            model=result.model,
            prompt_version=result.prompt_version,
            payload_json=result.payload_json,
            failure_json=result.failure_json,
        )
        return {
            "case_id": case_id,
            "record_status": result.status.value,
        }
    finally:
        session.close()
