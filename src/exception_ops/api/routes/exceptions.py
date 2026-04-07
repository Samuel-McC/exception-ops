from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from exception_ops.db import get_session
from exception_ops.db.repositories import create_exception_case, get_exception_case_detail, list_exception_cases
from exception_ops.domain.enums import AuditEventType, ExceptionStatus, ExceptionType, RiskLevel
from exception_ops.domain.models import AuditEvent, ExceptionCase

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
    created_at: datetime
    updated_at: datetime


class ExceptionCaseDetailResponse(ExceptionCaseResponse):
    audit_history: list[AuditEventResponse] = Field(default_factory=list)


class ExceptionCaseListResponse(BaseModel):
    items: list[ExceptionCaseResponse]


@router.post("", response_model=ExceptionCaseDetailResponse, status_code=status.HTTP_201_CREATED)
def create_exception(
    request: CreateExceptionRequest,
    session: Session = Depends(get_session),
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
    return _build_exception_case_detail_response(exception_case, audit_history)


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
    return _build_exception_case_detail_response(exception_case, audit_history)


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
        created_at=exception_case.created_at,
        updated_at=exception_case.updated_at,
    )


def _build_exception_case_detail_response(
    exception_case: ExceptionCase,
    audit_history: list[AuditEvent],
) -> ExceptionCaseDetailResponse:
    return ExceptionCaseDetailResponse(
        **_build_exception_case_response(exception_case).model_dump(),
        audit_history=[_build_audit_event_response(event) for event in audit_history],
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
