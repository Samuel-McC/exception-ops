from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from exception_ops.ai.schemas import ClassificationOutput, RemediationPlanOutput
from exception_ops.db import get_session
from exception_ops.db.repositories import (
    create_exception_case,
    get_exception_case_detail,
    get_latest_ai_records,
    list_exception_cases,
    update_exception_case_workflow,
)
from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    AuditEventType,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)
from exception_ops.domain.models import AIRecord, AuditEvent, ExceptionCase
from exception_ops.temporal import (
    WorkflowStartError,
    WorkflowStarter,
    build_exception_workflow_id,
    get_workflow_starter,
)

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


class CreateExceptionRequest(BaseModel):
    exception_type: ExceptionType
    risk_level: RiskLevel
    summary: str = Field(min_length=1, max_length=2000)
    source_system: str = Field(min_length=1, max_length=255)
    external_reference: str | None = Field(default=None, max_length=255)
    raw_context_json: dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    event_id: str
    case_id: str
    event_type: AuditEventType
    actor: str
    payload_json: dict[str, Any]
    created_at: datetime


class ExceptionCaseResponse(BaseModel):
    case_id: str
    exception_type: ExceptionType
    status: ExceptionStatus
    risk_level: RiskLevel
    summary: str
    source_system: str
    external_reference: str | None
    raw_context_json: dict[str, Any]
    temporal_workflow_id: str | None
    temporal_run_id: str | None
    workflow_lifecycle_state: WorkflowLifecycleState
    created_at: datetime
    updated_at: datetime


class ClassificationRecordResponse(BaseModel):
    record_id: str
    status: AIRecordStatus
    provider: str
    model: str
    prompt_version: str
    output: ClassificationOutput | None
    failure: dict[str, Any] | None
    created_at: datetime


class RemediationRecordResponse(BaseModel):
    record_id: str
    status: AIRecordStatus
    provider: str
    model: str
    prompt_version: str
    output: RemediationPlanOutput | None
    failure: dict[str, Any] | None
    created_at: datetime


class ExceptionCaseDetailResponse(ExceptionCaseResponse):
    audit_history: list[AuditEventResponse] = Field(default_factory=list)
    latest_classification: ClassificationRecordResponse | None = None
    latest_remediation: RemediationRecordResponse | None = None


class ExceptionCaseListResponse(BaseModel):
    items: list[ExceptionCaseResponse]


@router.post("", response_model=ExceptionCaseDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_exception(
    request: CreateExceptionRequest,
    session: Session = Depends(get_session),
    workflow_starter: WorkflowStarter = Depends(get_workflow_starter),
) -> ExceptionCaseDetailResponse:
    exception_case, audit_history = create_exception_case(
        session,
        exception_type=request.exception_type,
        risk_level=request.risk_level,
        summary=request.summary,
        source_system=request.source_system,
        external_reference=request.external_reference,
        raw_context_json=request.raw_context_json,
    )
    workflow_id = build_exception_workflow_id(exception_case.case_id)

    try:
        workflow_start = await workflow_starter.start_exception_workflow(
            exception_case.case_id,
            workflow_id,
        )
        exception_case = update_exception_case_workflow(
            session,
            case_id=exception_case.case_id,
            temporal_workflow_id=workflow_start.workflow_id,
            temporal_run_id=workflow_start.run_id,
            workflow_lifecycle_state=WorkflowLifecycleState.STARTED,
        )
    except WorkflowStartError:
        exception_case = update_exception_case_workflow(
            session,
            case_id=exception_case.case_id,
            temporal_workflow_id=workflow_id,
            temporal_run_id=None,
            workflow_lifecycle_state=WorkflowLifecycleState.FAILED,
        )

    return _build_exception_case_detail_response(
        exception_case,
        audit_history,
        latest_ai_records={},
    )


@router.get("", response_model=ExceptionCaseListResponse)
def get_exceptions(session: Session = Depends(get_session)) -> ExceptionCaseListResponse:
    items = [_build_exception_case_response(item) for item in list_exception_cases(session)]
    return ExceptionCaseListResponse(items=items)


@router.get("/{case_id}", response_model=ExceptionCaseDetailResponse)
def get_exception(case_id: str, session: Session = Depends(get_session)) -> ExceptionCaseDetailResponse:
    detail = get_exception_case_detail(session, case_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception case not found")

    exception_case, audit_history = detail
    latest_ai_records = get_latest_ai_records(session, case_id)
    return _build_exception_case_detail_response(exception_case, audit_history, latest_ai_records)


def _build_exception_case_response(exception_case: ExceptionCase) -> ExceptionCaseResponse:
    return ExceptionCaseResponse(
        case_id=exception_case.case_id,
        exception_type=exception_case.exception_type,
        status=exception_case.status,
        risk_level=exception_case.risk_level,
        summary=exception_case.summary,
        source_system=exception_case.source_system,
        external_reference=exception_case.external_reference,
        raw_context_json=exception_case.raw_context_json,
        temporal_workflow_id=exception_case.temporal_workflow_id,
        temporal_run_id=exception_case.temporal_run_id,
        workflow_lifecycle_state=exception_case.workflow_lifecycle_state,
        created_at=exception_case.created_at,
        updated_at=exception_case.updated_at,
    )


def _build_exception_case_detail_response(
    exception_case: ExceptionCase,
    audit_history: list[AuditEvent],
    latest_ai_records: dict[AIRecordKind, AIRecord],
) -> ExceptionCaseDetailResponse:
    return ExceptionCaseDetailResponse(
        **_build_exception_case_response(exception_case).model_dump(),
        audit_history=[_build_audit_event_response(event) for event in audit_history],
        latest_classification=_build_classification_record_response(
            latest_ai_records.get(AIRecordKind.CLASSIFICATION)
        ),
        latest_remediation=_build_remediation_record_response(
            latest_ai_records.get(AIRecordKind.REMEDIATION)
        ),
    )


def _build_audit_event_response(audit_event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        event_id=audit_event.event_id,
        case_id=audit_event.case_id,
        event_type=audit_event.event_type,
        actor=audit_event.actor,
        payload_json=audit_event.payload_json,
        created_at=audit_event.created_at,
    )


def _build_classification_record_response(
    ai_record: AIRecord | None,
) -> ClassificationRecordResponse | None:
    if ai_record is None:
        return None

    output = _validate_ai_payload(ai_record, ClassificationOutput)
    return ClassificationRecordResponse(
        record_id=ai_record.record_id,
        status=ai_record.status,
        provider=ai_record.provider,
        model=ai_record.model,
        prompt_version=ai_record.prompt_version,
        output=output,
        failure=_build_failure_payload(ai_record, output is None),
        created_at=ai_record.created_at,
    )


def _build_remediation_record_response(
    ai_record: AIRecord | None,
) -> RemediationRecordResponse | None:
    if ai_record is None:
        return None

    output = _validate_ai_payload(ai_record, RemediationPlanOutput)
    return RemediationRecordResponse(
        record_id=ai_record.record_id,
        status=ai_record.status,
        provider=ai_record.provider,
        model=ai_record.model,
        prompt_version=ai_record.prompt_version,
        output=output,
        failure=_build_failure_payload(ai_record, output is None),
        created_at=ai_record.created_at,
    )


def _validate_ai_payload(ai_record: AIRecord, payload_model: type[BaseModel]) -> BaseModel | None:
    if ai_record.payload_json is None:
        return None

    try:
        return payload_model.model_validate(ai_record.payload_json)
    except ValidationError:
        return None


def _build_failure_payload(ai_record: AIRecord, payload_invalid: bool) -> dict[str, Any] | None:
    if ai_record.failure_json is not None:
        return ai_record.failure_json
    if payload_invalid:
        return {
            "type": "payload_validation_error",
            "message": "Stored AI payload did not match the expected schema.",
        }
    return None
