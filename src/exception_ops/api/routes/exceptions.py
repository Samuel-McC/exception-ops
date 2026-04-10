from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from exception_ops.api.exception_cases import (
    ApprovalDecisionRequest,
    ExceptionCaseDetailResponse,
    ExceptionCaseListResponse,
    build_exception_case_detail_from_parts,
    build_exception_case_detail_response,
    build_exception_case_response,
    load_exception_case_detail_or_404,
    submit_approval_decision,
)
from exception_ops.auth import OperatorIdentity, OperatorRole, require_api_roles
from exception_ops.db import get_session
from exception_ops.db.repositories import create_exception_case, list_exception_cases, update_exception_case_workflow
from exception_ops.domain.enums import ApprovalDecisionType, ExceptionType, RiskLevel, WorkflowLifecycleState
from exception_ops.temporal import (
    WorkflowSignaler,
    WorkflowStartError,
    WorkflowStarter,
    build_exception_workflow_id,
    get_workflow_signaler,
    get_workflow_starter,
)

router = APIRouter(prefix="/exceptions", tags=["exceptions"])
require_review_access = require_api_roles(
    OperatorRole.REVIEWER,
    OperatorRole.APPROVER,
    OperatorRole.EXECUTOR,
    OperatorRole.ADMIN,
)
require_approval_access = require_api_roles(
    OperatorRole.APPROVER,
    OperatorRole.ADMIN,
)


class CreateExceptionRequest(BaseModel):
    exception_type: ExceptionType
    risk_level: RiskLevel
    summary: str = Field(min_length=1, max_length=2000)
    source_system: str = Field(min_length=1, max_length=255)
    external_reference: str | None = Field(default=None, max_length=255)
    raw_context_json: dict[str, Any] = Field(default_factory=dict)


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

    return build_exception_case_detail_from_parts(
        exception_case=exception_case,
        audit_history=audit_history,
        latest_ai_records={},
        approval_history=[],
        execution_history=[],
    )


@router.get("", response_model=ExceptionCaseListResponse)
def get_exceptions(
    session: Session = Depends(get_session),
    _: OperatorIdentity = Depends(require_review_access),
) -> ExceptionCaseListResponse:
    items = [build_exception_case_response(item) for item in list_exception_cases(session)]
    return ExceptionCaseListResponse(items=items)


@router.get("/{case_id}", response_model=ExceptionCaseDetailResponse)
def get_exception(
    case_id: str,
    session: Session = Depends(get_session),
    _: OperatorIdentity = Depends(require_review_access),
) -> ExceptionCaseDetailResponse:
    return build_exception_case_detail_response(load_exception_case_detail_or_404(session, case_id))


@router.post("/{case_id}/approve", response_model=ExceptionCaseDetailResponse)
async def approve_exception(
    case_id: str,
    request: ApprovalDecisionRequest,
    session: Session = Depends(get_session),
    workflow_signaler: WorkflowSignaler = Depends(get_workflow_signaler),
    operator: OperatorIdentity = Depends(require_approval_access),
) -> ExceptionCaseDetailResponse:
    return await submit_approval_decision(
        session=session,
        workflow_signaler=workflow_signaler,
        case_id=case_id,
        decision=ApprovalDecisionType.APPROVED,
        actor=operator.username,
        request=request,
    )


@router.post("/{case_id}/reject", response_model=ExceptionCaseDetailResponse)
async def reject_exception(
    case_id: str,
    request: ApprovalDecisionRequest,
    session: Session = Depends(get_session),
    workflow_signaler: WorkflowSignaler = Depends(get_workflow_signaler),
    operator: OperatorIdentity = Depends(require_approval_access),
) -> ExceptionCaseDetailResponse:
    return await submit_approval_decision(
        session=session,
        workflow_signaler=workflow_signaler,
        case_id=case_id,
        decision=ApprovalDecisionType.REJECTED,
        actor=operator.username,
        request=request,
    )
