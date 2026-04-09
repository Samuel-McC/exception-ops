from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from exception_ops.db.models import (
    AIRecordRecord,
    ApprovalDecisionRecord,
    AuditEventRecord,
    ExceptionCaseRecord,
)
from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    ApprovalDecisionType,
    ApprovalState,
    AuditEventType,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)
from exception_ops.domain.models import AIRecord, ApprovalDecision, AuditEvent, ExceptionCase


INGEST_ACTOR = "system:api"


def create_exception_case(
    session: Session,
    *,
    exception_type: ExceptionType,
    risk_level: RiskLevel,
    summary: str,
    source_system: str,
    external_reference: str | None,
    raw_context_json: dict[str, Any],
    actor: str = INGEST_ACTOR,
) -> tuple[ExceptionCase, list[AuditEvent]]:
    case_id = str(uuid4())
    exception_case = ExceptionCaseRecord(
        case_id=case_id,
        exception_type=exception_type,
        status=ExceptionStatus.INGESTED,
        risk_level=risk_level,
        summary=summary,
        source_system=source_system,
        external_reference=external_reference,
        raw_context_json=dict(raw_context_json),
        workflow_lifecycle_state=WorkflowLifecycleState.STARTED,
        approval_state=ApprovalState.PENDING_POLICY,
    )
    audit_event = AuditEventRecord(
        event_id=str(uuid4()),
        case_id=case_id,
        event_type=AuditEventType.INGESTED,
        actor=actor,
        payload_json={
            "exception_type": exception_type.value,
            "source_system": source_system,
            "external_reference": external_reference,
        },
    )
    exception_case.audit_events.append(audit_event)

    session.add(exception_case)
    session.commit()
    session.refresh(exception_case)
    session.refresh(audit_event)

    return _to_domain_case(exception_case), [_to_domain_audit_event(audit_event)]


def update_exception_case_workflow(
    session: Session,
    *,
    case_id: str,
    temporal_workflow_id: str,
    workflow_lifecycle_state: WorkflowLifecycleState,
    temporal_run_id: str | None = None,
) -> ExceptionCase:
    record = session.get(ExceptionCaseRecord, case_id)
    if record is None:
        raise ValueError(f"Exception case not found: {case_id}")

    record.temporal_workflow_id = temporal_workflow_id
    record.temporal_run_id = temporal_run_id
    record.workflow_lifecycle_state = workflow_lifecycle_state

    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_domain_case(record)


def update_exception_case_state(
    session: Session,
    *,
    case_id: str,
    workflow_lifecycle_state: WorkflowLifecycleState | None = None,
    approval_state: ApprovalState | None = None,
    status: ExceptionStatus | None = None,
) -> ExceptionCase:
    record = session.get(ExceptionCaseRecord, case_id)
    if record is None:
        raise ValueError(f"Exception case not found: {case_id}")

    if workflow_lifecycle_state is not None:
        record.workflow_lifecycle_state = workflow_lifecycle_state
    if approval_state is not None:
        record.approval_state = approval_state
    if status is not None:
        record.status = status

    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_domain_case(record)


def create_ai_record(
    session: Session,
    *,
    case_id: str,
    record_kind: AIRecordKind,
    status: AIRecordStatus,
    provider: str,
    model: str,
    prompt_version: str,
    payload_json: dict[str, Any] | None = None,
    failure_json: dict[str, Any] | None = None,
) -> AIRecord:
    record = AIRecordRecord(
        record_id=str(uuid4()),
        case_id=case_id,
        record_kind=record_kind,
        status=status,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        payload_json=dict(payload_json) if payload_json is not None else None,
        failure_json=dict(failure_json) if failure_json is not None else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_domain_ai_record(record)


def create_approval_decision(
    session: Session,
    *,
    case_id: str,
    decision: ApprovalDecisionType,
    actor: str,
    reason: str,
) -> tuple[ExceptionCase, ApprovalDecision]:
    case_record = session.get(ExceptionCaseRecord, case_id)
    if case_record is None:
        raise ValueError(f"Exception case not found: {case_id}")
    if case_record.approval_state is not ApprovalState.PENDING:
        raise ValueError(f"Case {case_id} is not waiting for an approval decision")

    target_state = (
        ApprovalState.APPROVED
        if decision is ApprovalDecisionType.APPROVED
        else ApprovalState.REJECTED
    )
    record = ApprovalDecisionRecord(
        decision_id=str(uuid4()),
        case_id=case_id,
        decision=decision,
        actor=actor,
        reason=reason,
    )

    case_record.approval_state = target_state
    case_record.status = ExceptionStatus.IN_REVIEW

    session.add(case_record)
    session.add(record)
    session.commit()
    session.refresh(case_record)
    session.refresh(record)
    return _to_domain_case(case_record), _to_domain_approval_decision(record)


def apply_approval_decision(
    session: Session,
    *,
    decision_id: str,
) -> tuple[ExceptionCase, ApprovalDecision]:
    decision_record = session.get(ApprovalDecisionRecord, decision_id)
    if decision_record is None:
        raise ValueError(f"Approval decision not found: {decision_id}")

    case_record = session.get(ExceptionCaseRecord, decision_record.case_id)
    if case_record is None:
        raise ValueError(f"Exception case not found: {decision_record.case_id}")

    target_state = (
        ApprovalState.APPROVED
        if decision_record.decision is ApprovalDecisionType.APPROVED
        else ApprovalState.REJECTED
    )
    if case_record.approval_state not in {ApprovalState.PENDING, target_state}:
        raise ValueError(
            f"Case {case_record.case_id} is not waiting for an approval decision"
        )

    case_record.approval_state = target_state
    case_record.workflow_lifecycle_state = WorkflowLifecycleState.COMPLETED
    case_record.status = ExceptionStatus.IN_REVIEW

    session.add(case_record)
    session.commit()
    session.refresh(case_record)
    session.refresh(decision_record)

    return _to_domain_case(case_record), _to_domain_approval_decision(decision_record)


def list_exception_cases(session: Session) -> list[ExceptionCase]:
    statement = select(ExceptionCaseRecord).order_by(ExceptionCaseRecord.created_at.desc())
    records = session.scalars(statement).all()
    return [_to_domain_case(record) for record in records]


def get_exception_case(session: Session, case_id: str) -> ExceptionCase | None:
    record = session.get(ExceptionCaseRecord, case_id)
    if record is None:
        return None
    return _to_domain_case(record)


def get_exception_case_detail(session: Session, case_id: str) -> tuple[ExceptionCase, list[AuditEvent]] | None:
    statement = (
        select(ExceptionCaseRecord)
        .options(selectinload(ExceptionCaseRecord.audit_events))
        .where(ExceptionCaseRecord.case_id == case_id)
    )
    record = session.scalar(statement)
    if record is None:
        return None

    return _to_domain_case(record), [_to_domain_audit_event(event) for event in record.audit_events]


def get_latest_ai_record(
    session: Session,
    case_id: str,
    record_kind: AIRecordKind,
) -> AIRecord | None:
    statement = (
        select(AIRecordRecord)
        .where(AIRecordRecord.case_id == case_id, AIRecordRecord.record_kind == record_kind)
        .order_by(AIRecordRecord.created_at.desc())
    )
    record = session.scalar(statement)
    if record is None:
        return None
    return _to_domain_ai_record(record)


def get_latest_ai_records(session: Session, case_id: str) -> dict[AIRecordKind, AIRecord]:
    statement = (
        select(AIRecordRecord)
        .where(AIRecordRecord.case_id == case_id)
        .order_by(AIRecordRecord.created_at.desc())
    )
    records = session.scalars(statement).all()

    latest: dict[AIRecordKind, AIRecord] = {}
    for record in records:
        latest.setdefault(record.record_kind, _to_domain_ai_record(record))

    return latest


def get_latest_approval_decision(session: Session, case_id: str) -> ApprovalDecision | None:
    statement = (
        select(ApprovalDecisionRecord)
        .where(ApprovalDecisionRecord.case_id == case_id)
        .order_by(ApprovalDecisionRecord.decided_at.desc())
    )
    record = session.scalar(statement)
    if record is None:
        return None
    return _to_domain_approval_decision(record)


def list_approval_decisions(session: Session, case_id: str) -> list[ApprovalDecision]:
    statement = (
        select(ApprovalDecisionRecord)
        .where(ApprovalDecisionRecord.case_id == case_id)
        .order_by(ApprovalDecisionRecord.decided_at.desc())
    )
    records = session.scalars(statement).all()
    return [_to_domain_approval_decision(record) for record in records]


def _to_domain_case(record: ExceptionCaseRecord) -> ExceptionCase:
    return ExceptionCase(
        case_id=record.case_id,
        exception_type=record.exception_type,
        status=record.status,
        risk_level=record.risk_level,
        summary=record.summary,
        source_system=record.source_system,
        external_reference=record.external_reference,
        raw_context_json=dict(record.raw_context_json or {}),
        temporal_workflow_id=record.temporal_workflow_id,
        temporal_run_id=record.temporal_run_id,
        workflow_lifecycle_state=record.workflow_lifecycle_state,
        approval_state=record.approval_state,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_domain_ai_record(record: AIRecordRecord) -> AIRecord:
    return AIRecord(
        record_id=record.record_id,
        case_id=record.case_id,
        record_kind=record.record_kind,
        status=record.status,
        provider=record.provider,
        model=record.model,
        prompt_version=record.prompt_version,
        payload_json=dict(record.payload_json) if record.payload_json is not None else None,
        failure_json=dict(record.failure_json) if record.failure_json is not None else None,
        created_at=record.created_at,
    )


def _to_domain_audit_event(record: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        event_id=record.event_id,
        case_id=record.case_id,
        event_type=record.event_type,
        actor=record.actor,
        payload_json=dict(record.payload_json or {}),
        created_at=record.created_at,
    )


def _to_domain_approval_decision(record: ApprovalDecisionRecord) -> ApprovalDecision:
    return ApprovalDecision(
        decision_id=record.decision_id,
        case_id=record.case_id,
        decision=record.decision,
        actor=record.actor,
        reason=record.reason,
        decided_at=record.decided_at,
    )
