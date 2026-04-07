from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from exception_ops.db.models import AuditEventRecord, ExceptionCaseRecord
from exception_ops.domain.enums import (
    AuditEventType,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)
from exception_ops.domain.models import AuditEvent, ExceptionCase


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
        workflow_lifecycle_state=WorkflowLifecycleState.NOT_STARTED,
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
        created_at=record.created_at,
        updated_at=record.updated_at,
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
