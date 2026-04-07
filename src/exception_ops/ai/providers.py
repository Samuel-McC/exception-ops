from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from exception_ops.ai.schemas import ClassificationOutput, RemediationPlanOutput
from exception_ops.domain.enums import ExceptionType, RiskLevel

ModelT = TypeVar("ModelT", bound=BaseModel)
MOCK_MODEL_NAME = "mock-heuristic-v1"


class ProviderConfigurationError(Exception):
    pass


@dataclass(slots=True)
class ProviderMetadata:
    provider: str
    model: str


class AIProvider(Protocol):
    metadata: ProviderMetadata

    async def generate_structured(
        self,
        *,
        task_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        prompt_context: dict[str, Any],
        response_model: type[ModelT],
    ) -> ModelT:
        ...


class MockAIProvider:
    def __init__(self) -> None:
        self.metadata = ProviderMetadata(provider="mock", model=MOCK_MODEL_NAME)

    async def generate_structured(
        self,
        *,
        task_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        prompt_context: dict[str, Any],
        response_model: type[ModelT],
    ) -> ModelT:
        del prompt_version, system_prompt, user_prompt

        if response_model is ClassificationOutput:
            payload = _mock_classification_payload(prompt_context)
        elif response_model is RemediationPlanOutput:
            payload = _mock_remediation_payload(prompt_context)
        else:
            raise ProviderConfigurationError(f"Unsupported mock response model for task {task_name}")

        return response_model.model_validate(payload)


class OpenAIProvider:
    def __init__(self, *, model: str, api_key: str) -> None:
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

        self.metadata = ProviderMetadata(provider="openai", model=model)
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate_structured(
        self,
        *,
        task_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        prompt_context: dict[str, Any],
        response_model: type[ModelT],
    ) -> ModelT:
        del task_name, prompt_version, prompt_context

        response = await self._client.responses.parse(
            model=self.metadata.model,
            instructions=system_prompt,
            input=user_prompt,
            text_format=response_model,
            temperature=0,
        )
        if response.output_parsed is None:
            raise RuntimeError("OpenAI returned no structured output")
        return response.output_parsed


def _mock_classification_payload(prompt_context: dict[str, Any]) -> dict[str, Any]:
    summary = str(prompt_context.get("summary", "")).lower()
    source_system = str(prompt_context.get("source_system", "unknown"))
    original_type = str(prompt_context.get("exception_type", ExceptionType.UNKNOWN.value))
    normalized_type = original_type

    if original_type == ExceptionType.UNKNOWN.value:
        if "document" in summary:
            normalized_type = ExceptionType.MISSING_DOCUMENT.value
        elif "duplicate" in summary:
            normalized_type = ExceptionType.DUPLICATE_RECORD_RISK.value
        elif "payout" in summary or "reconciliation" in summary:
            normalized_type = ExceptionType.PAYOUT_MISMATCH.value
        elif "provider" in summary or "timeout" in summary or "502" in summary:
            normalized_type = ExceptionType.PROVIDER_FAILURE.value

    confidence = 0.9 if normalized_type == original_type and original_type != ExceptionType.UNKNOWN.value else 0.68
    missing_information = []
    if not prompt_context.get("external_reference"):
        missing_information.append("external_reference")

    return {
        "normalized_exception_type": normalized_type,
        "confidence": confidence,
        "risk_level_suggestion": str(prompt_context.get("risk_level", RiskLevel.LOW.value)),
        "reasoning_summary": (
            f"Mock classification used the stored exception type and summary for source system "
            f"{source_system}."
        ),
        "missing_information": missing_information,
    }


def _mock_remediation_payload(prompt_context: dict[str, Any]) -> dict[str, Any]:
    classification = prompt_context.get("classification") or {}
    normalized_type = str(
        classification.get("normalized_exception_type", prompt_context.get("exception_type", ExceptionType.UNKNOWN.value))
    )
    execution_risk = str(
        classification.get("risk_level_suggestion", prompt_context.get("risk_level", RiskLevel.LOW.value))
    )

    action_map = {
        ExceptionType.PAYOUT_MISMATCH.value: "review_payout_reconciliation",
        ExceptionType.MISSING_DOCUMENT.value: "request_missing_document",
        ExceptionType.DUPLICATE_RECORD_RISK.value: "review_duplicate_records",
        ExceptionType.PROVIDER_FAILURE.value: "retry_provider_after_validation",
        ExceptionType.UNKNOWN.value: "manual_triage",
    }
    blockers = []
    if not prompt_context.get("external_reference"):
        blockers.append("external_reference_missing")

    return {
        "recommended_action": action_map.get(normalized_type, "manual_triage"),
        "operator_summary": (
            f"Mock remediation suggests operator review for {normalized_type} from "
            f"{prompt_context.get('source_system', 'unknown')}."
        ),
        "rationale": (
            "This bounded mock remediation plan is derived from the stored exception context and any "
            "available classification output."
        ),
        "execution_risk": execution_risk,
        "requires_approval": execution_risk in {RiskLevel.MEDIUM.value, RiskLevel.HIGH.value},
        "blockers": blockers,
    }
