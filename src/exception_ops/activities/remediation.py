from __future__ import annotations

from pydantic import ValidationError
from temporalio import activity

from exception_ops.ai.schemas import ClassificationOutput
from exception_ops.ai.service import get_ai_service
from exception_ops.db import get_session_factory
from exception_ops.db.repositories import (
    create_ai_record,
    get_exception_case,
    get_latest_ai_record,
    list_evidence_records,
)
from exception_ops.domain.enums import AIRecordKind, AIRecordStatus


@activity.defn
async def generate_remediation_plan(case_id: str) -> dict[str, str]:
    session = get_session_factory()()
    try:
        exception_case = get_exception_case(session, case_id)
        if exception_case is None:
            raise ValueError(f"Exception case not found: {case_id}")

        classification_record = get_latest_ai_record(session, case_id, AIRecordKind.CLASSIFICATION)
        classification_output = None
        classification_status = AIRecordStatus.FAILED
        if classification_record is not None:
            classification_status = classification_record.status
            if (
                classification_record.status is AIRecordStatus.SUCCEEDED
                and classification_record.payload_json is not None
            ):
                try:
                    classification_output = ClassificationOutput.model_validate(
                        classification_record.payload_json
                    )
                except ValidationError:
                    classification_status = AIRecordStatus.FAILED

        evidence_records = list(reversed(list_evidence_records(session, case_id)))
        result = await get_ai_service().generate_remediation_plan(
            exception_case,
            classification_output,
            evidence_records,
        )
        create_ai_record(
            session,
            case_id=case_id,
            record_kind=AIRecordKind.REMEDIATION,
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
            "classification_record_status": classification_status.value,
        }
    finally:
        session.close()
