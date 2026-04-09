from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from exception_ops.config import settings
from exception_ops.domain.enums import ExecutionAction
from exception_ops.domain.models import ExceptionCase


@dataclass(slots=True)
class ExecutionAdapterMetadata:
    adapter: str


@dataclass(slots=True)
class ExecutionAdapterResult:
    result_payload_json: dict[str, Any] | None = None
    failure_payload_json: dict[str, Any] | None = None


class ExecutionAdapterConfigurationError(Exception):
    pass


class ExecutionAdapter(Protocol):
    metadata: ExecutionAdapterMetadata

    async def execute(
        self,
        *,
        action_name: ExecutionAction,
        exception_case: ExceptionCase,
        request_payload_json: dict[str, Any],
    ) -> ExecutionAdapterResult:
        ...


class MockExecutionAdapter:
    def __init__(self) -> None:
        self.metadata = ExecutionAdapterMetadata(adapter="mock")

    async def execute(
        self,
        *,
        action_name: ExecutionAction,
        exception_case: ExceptionCase,
        request_payload_json: dict[str, Any],
    ) -> ExecutionAdapterResult:
        if exception_case.raw_context_json.get("force_execution_failure"):
            return ExecutionAdapterResult(
                failure_payload_json={
                    "type": "mock_execution_failure",
                    "message": f"Mock execution failed for action {action_name.value}.",
                }
            )

        action_results = {
            ExecutionAction.RETRY_PROVIDER_AFTER_VALIDATION: {
                "outcome": "provider_retry_requested",
                "source_system": exception_case.source_system,
            },
            ExecutionAction.REQUEST_MISSING_DOCUMENT: {
                "outcome": "missing_document_request_queued",
                "external_reference": exception_case.external_reference,
            },
            ExecutionAction.REVIEW_DUPLICATE_RECORDS: {
                "outcome": "duplicate_record_review_queued",
                "source_system": exception_case.source_system,
            },
            ExecutionAction.REVIEW_PAYOUT_RECONCILIATION: {
                "outcome": "payout_reconciliation_review_queued",
                "external_reference": exception_case.external_reference,
            },
            ExecutionAction.MANUAL_TRIAGE: {
                "outcome": "manual_triage_required",
                "summary": exception_case.summary,
            },
        }
        return ExecutionAdapterResult(
            result_payload_json={
                "adapter": self.metadata.adapter,
                "action_name": action_name.value,
                "request": dict(request_payload_json),
                "result": action_results[action_name],
            }
        )


def get_execution_adapter() -> ExecutionAdapter:
    adapter_name = settings.execution_adapter.strip().lower()
    if adapter_name == "mock":
        return MockExecutionAdapter()
    raise ExecutionAdapterConfigurationError(
        f"Unsupported EXECUTION_ADAPTER value: {settings.execution_adapter}"
    )
