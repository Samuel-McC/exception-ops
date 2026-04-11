from __future__ import annotations

from temporalio import activity

from exception_ops.config import settings
from exception_ops.db import get_session_factory
from exception_ops.db.repositories import (
    create_evidence_record,
    get_exception_case,
    get_latest_execution_record,
)
from exception_ops.domain.enums import EvidenceSourceType, EvidenceStatus
from exception_ops.evidence_adapters import (
    EvidenceAdapterConfigurationError,
    get_evidence_adapter,
)

@activity.defn
async def collect_evidence(case_id: str) -> dict[str, int | str]:
    session = get_session_factory()()
    try:
        exception_case = get_exception_case(session, case_id)
        if exception_case is None:
            raise ValueError(f"Exception case not found: {case_id}")

        latest_execution_record = get_latest_execution_record(session, case_id)
        configured_adapter_name = _configured_evidence_adapter_name()
        try:
            adapter = get_evidence_adapter()
            configured_adapter_name = adapter.metadata.adapter
            result = await adapter.collect(
                exception_case=exception_case,
                latest_execution_record=latest_execution_record,
            )
        except (EvidenceAdapterConfigurationError, RuntimeError, ValueError) as exc:
            failure_stage = (
                "adapter_initialization"
                if isinstance(exc, EvidenceAdapterConfigurationError)
                else "adapter_collect"
            )
            create_evidence_record(
                session,
                case_id=case_id,
                source_type=EvidenceSourceType.COLLECTION_ATTEMPT,
                source_name="evidence_collection",
                adapter_name=configured_adapter_name,
                status=EvidenceStatus.FAILED,
                summary_text="Evidence collection failed before any evidence item was persisted.",
                provenance_json={
                    "reference_id": case_id,
                    "request": "collect_evidence",
                },
                failure_json=_normalize_evidence_failure_payload(
                    {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                    adapter_name=configured_adapter_name,
                    stage=failure_stage,
                    source_name="evidence_collection",
                ),
            )
            return {
                "case_id": case_id,
                "items_collected": 0,
                "items_failed": 1,
            }

        items_collected = 0
        items_failed = 0
        for item in result.items:
            create_evidence_record(
                session,
                case_id=case_id,
                source_type=item.source_type,
                source_name=item.source_name,
                adapter_name=adapter.metadata.adapter,
                status=item.status,
                payload_json=item.payload_json,
                summary_text=item.summary_text,
                provenance_json=item.provenance_json,
                failure_json=(
                    _normalize_evidence_failure_payload(
                        item.failure_json,
                        adapter_name=adapter.metadata.adapter,
                        stage="adapter_item",
                        source_name=item.source_name,
                    )
                    if item.status is EvidenceStatus.FAILED or item.failure_json is not None
                    else None
                ),
            )
            if item.status is EvidenceStatus.SUCCEEDED:
                items_collected += 1
            else:
                items_failed += 1

        return {
            "case_id": case_id,
            "items_collected": items_collected,
            "items_failed": items_failed,
        }
    finally:
        session.close()


def _configured_evidence_adapter_name() -> str:
    adapter_name = settings.evidence_adapter.strip().lower()
    return adapter_name or "unknown"


def _normalize_evidence_failure_payload(
    failure_json: dict[str, str] | None,
    *,
    adapter_name: str,
    stage: str,
    source_name: str,
) -> dict[str, str]:
    payload = dict(failure_json or {})
    payload.setdefault("type", "EvidenceCollectionFailure")
    payload.setdefault("message", "Evidence collection failed.")
    payload["adapter_name"] = adapter_name
    payload["stage"] = stage
    payload["source_name"] = source_name
    return payload
