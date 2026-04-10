from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from exception_ops.config import settings
from exception_ops.domain.enums import EvidenceSourceType, EvidenceStatus, ExceptionType
from exception_ops.domain.models import ExceptionCase, ExecutionRecord


@dataclass(slots=True)
class EvidenceAdapterMetadata:
    adapter: str


@dataclass(slots=True)
class EvidenceItem:
    source_type: EvidenceSourceType
    source_name: str
    status: EvidenceStatus
    payload_json: dict[str, Any] | None = None
    summary_text: str | None = None
    provenance_json: dict[str, Any] = field(default_factory=dict)
    failure_json: dict[str, Any] | None = None


@dataclass(slots=True)
class EvidenceAdapterResult:
    items: list[EvidenceItem]


class EvidenceAdapterConfigurationError(Exception):
    pass


class EvidenceAdapter(Protocol):
    metadata: EvidenceAdapterMetadata

    async def collect(
        self,
        *,
        exception_case: ExceptionCase,
        latest_execution_record: ExecutionRecord | None,
    ) -> EvidenceAdapterResult:
        ...


class MockEvidenceAdapter:
    def __init__(self) -> None:
        self.metadata = EvidenceAdapterMetadata(adapter="mock")

    async def collect(
        self,
        *,
        exception_case: ExceptionCase,
        latest_execution_record: ExecutionRecord | None,
    ) -> EvidenceAdapterResult:
        raw_context = exception_case.raw_context_json
        if raw_context.get("force_evidence_failure"):
            raise RuntimeError("Mock evidence adapter failed before collecting evidence.")

        items = [
            EvidenceItem(
                source_type=EvidenceSourceType.CASE_PAYLOAD_SNAPSHOT,
                source_name="ingest_payload",
                status=EvidenceStatus.SUCCEEDED,
                payload_json={
                    "summary": exception_case.summary,
                    "source_system": exception_case.source_system,
                    "external_reference": exception_case.external_reference,
                    "raw_context_json": dict(exception_case.raw_context_json),
                },
                summary_text="Captured source exception payload from ingest.",
                provenance_json={
                    "reference_id": exception_case.case_id,
                    "request": "source_case_snapshot",
                },
            )
        ]

        items.append(_build_related_lookup_item(exception_case))

        if raw_context.get("force_related_lookup_failure"):
            items.append(
                EvidenceItem(
                    source_type=EvidenceSourceType.INTERNAL_REFERENCE_LOOKUP,
                    source_name="related_internal_lookup",
                    status=EvidenceStatus.FAILED,
                    summary_text="Failed to collect the related internal reference lookup.",
                    provenance_json={
                        "reference_id": exception_case.external_reference or exception_case.case_id,
                        "request": "related_internal_lookup",
                    },
                    failure_json={
                        "type": "mock_related_lookup_failure",
                        "message": "The mock adapter was instructed to fail the related lookup.",
                    },
                )
            )

        if latest_execution_record is not None:
            items.append(
                EvidenceItem(
                    source_type=EvidenceSourceType.PRIOR_EXECUTION_SNAPSHOT,
                    source_name="latest_execution_record",
                    status=EvidenceStatus.SUCCEEDED,
                    payload_json={
                        "execution_id": latest_execution_record.execution_id,
                        "action_name": latest_execution_record.action_name.value,
                        "status": latest_execution_record.status.value,
                        "request_payload_json": dict(latest_execution_record.request_payload_json),
                        "result_payload_json": (
                            dict(latest_execution_record.result_payload_json)
                            if latest_execution_record.result_payload_json is not None
                            else None
                        ),
                    },
                    summary_text="Captured the most recent execution record for this case.",
                    provenance_json={
                        "reference_id": latest_execution_record.execution_id,
                        "request": "prior_execution_snapshot",
                    },
                )
            )

        return EvidenceAdapterResult(items=items)


def get_evidence_adapter() -> EvidenceAdapter:
    adapter_name = settings.evidence_adapter.strip().lower()
    if adapter_name == "mock":
        return MockEvidenceAdapter()
    raise EvidenceAdapterConfigurationError(
        f"Unsupported EVIDENCE_ADAPTER value: {settings.evidence_adapter}"
    )


def _build_related_lookup_item(exception_case: ExceptionCase) -> EvidenceItem:
    reference_id = exception_case.external_reference or exception_case.case_id
    raw_context = exception_case.raw_context_json

    if exception_case.exception_type is ExceptionType.MISSING_DOCUMENT:
        return EvidenceItem(
            source_type=EvidenceSourceType.DOCUMENT_METADATA,
            source_name="related_document_metadata",
            status=EvidenceStatus.SUCCEEDED,
            payload_json={
                "document_id": reference_id,
                "document_status": "missing",
                "requested_by": exception_case.source_system,
            },
            summary_text="Captured related document metadata for the missing-document case.",
            provenance_json={
                "reference_id": reference_id,
                "request": "related_document_metadata",
            },
        )

    if exception_case.exception_type is ExceptionType.PROVIDER_FAILURE:
        return EvidenceItem(
            source_type=EvidenceSourceType.PROVIDER_RESPONSE_SNAPSHOT,
            source_name="related_provider_response",
            status=EvidenceStatus.SUCCEEDED,
            payload_json={
                "provider_status": raw_context.get("provider_status", "502"),
                "attempt": raw_context.get("attempt"),
                "job_id": raw_context.get("job_id"),
                "external_reference": exception_case.external_reference,
            },
            summary_text="Captured the related provider response snapshot.",
            provenance_json={
                "reference_id": reference_id,
                "request": "related_provider_response",
            },
        )

    return EvidenceItem(
        source_type=EvidenceSourceType.INTERNAL_REFERENCE_LOOKUP,
        source_name="related_internal_lookup",
        status=EvidenceStatus.SUCCEEDED,
        payload_json={
            "lookup_key": reference_id,
            "source_system": exception_case.source_system,
            "risk_level": exception_case.risk_level.value,
        },
        summary_text="Captured a bounded internal reference lookup for the case.",
        provenance_json={
            "reference_id": reference_id,
            "request": "related_internal_lookup",
        },
    )
