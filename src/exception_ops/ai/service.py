from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from exception_ops.ai.providers import (
    MOCK_MODEL_NAME,
    AIProvider,
    MockAIProvider,
    OpenAIProvider,
    ProviderConfigurationError,
)
from exception_ops.ai.schemas import ClassificationOutput, RemediationPlanOutput
from exception_ops.config import settings
from exception_ops.domain.enums import AIRecordStatus
from exception_ops.domain.models import EvidenceRecord, ExceptionCase

CLASSIFICATION_PROMPT_VERSION = "classification.v2"
REMEDIATION_PROMPT_VERSION = "remediation.v2"


@dataclass(slots=True)
class AIInvocationResult:
    status: AIRecordStatus
    provider: str
    model: str
    prompt_version: str
    payload_json: dict[str, Any] | None = None
    failure_json: dict[str, Any] | None = None


class ExceptionAIService:
    async def classify_exception(
        self,
        exception_case: ExceptionCase,
        evidence_records: list[EvidenceRecord] | None = None,
    ) -> AIInvocationResult:
        prompt_context = _build_case_context(exception_case, evidence_records)
        system_prompt = (
            "You are ExceptionOps classification. Use the provided source case data as source truth and treat "
            "collected evidence as bounded supporting context only. Return a structured classification that "
            "matches the schema exactly. Do not recommend approval or execution."
        )
        user_prompt = (
            "Classify this exception into the bounded taxonomy and suggest a risk level using the source case "
            "data plus any collected evidence.\n\n"
            f"Prompt version: {CLASSIFICATION_PROMPT_VERSION}\n"
            f"Case context:\n{_to_json(prompt_context)}"
        )

        return await self._generate(
            task_name="classification",
            prompt_version=CLASSIFICATION_PROMPT_VERSION,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_context=prompt_context,
            response_model=ClassificationOutput,
        )

    async def generate_remediation_plan(
        self,
        exception_case: ExceptionCase,
        classification_output: ClassificationOutput | None,
        evidence_records: list[EvidenceRecord] | None = None,
    ) -> AIInvocationResult:
        prompt_context = _build_case_context(exception_case, evidence_records)
        if classification_output is not None:
            prompt_context["classification"] = classification_output.model_dump(mode="json")

        system_prompt = (
            "You are ExceptionOps remediation planning. Produce an advisory remediation plan only. "
            "Use the source case data as source truth and collected evidence as bounded supporting context. "
            "Do not approve or execute actions. Return a structured result that matches the schema exactly."
        )
        user_prompt = (
            "Generate an operator-facing remediation plan using the stored exception context, any collected "
            "evidence, and any available classification output.\n\n"
            f"Prompt version: {REMEDIATION_PROMPT_VERSION}\n"
            f"Case context:\n{_to_json(prompt_context)}"
        )

        return await self._generate(
            task_name="remediation",
            prompt_version=REMEDIATION_PROMPT_VERSION,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_context=prompt_context,
            response_model=RemediationPlanOutput,
        )

    async def _generate(
        self,
        *,
        task_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        prompt_context: dict[str, Any],
        response_model: type[BaseModel],
    ) -> AIInvocationResult:
        provider_name, model_name = _configured_provider_metadata()
        if not settings.ai_enabled:
            return _failure_result(
                provider=provider_name,
                model=model_name,
                prompt_version=prompt_version,
                failure_type="ai_disabled",
                message="AI generation is disabled by configuration.",
            )

        try:
            provider = _build_ai_provider()
            provider_name = provider.metadata.provider
            model_name = provider.metadata.model
            output = await provider.generate_structured(
                task_name=task_name,
                prompt_version=prompt_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_context=prompt_context,
                response_model=response_model,
            )
        except (OpenAIError, ProviderConfigurationError, RuntimeError, ValidationError, ValueError) as exc:
            return _failure_result(
                provider=provider_name,
                model=model_name,
                prompt_version=prompt_version,
                failure_type=type(exc).__name__,
                message=str(exc),
            )

        return AIInvocationResult(
            status=AIRecordStatus.SUCCEEDED,
            provider=provider_name,
            model=model_name,
            prompt_version=prompt_version,
            payload_json=output.model_dump(mode="json"),
        )


def get_ai_service() -> ExceptionAIService:
    return ExceptionAIService()


def _build_ai_provider() -> AIProvider:
    provider_name = settings.ai_provider.strip().lower()
    if provider_name == "mock":
        return MockAIProvider()
    if provider_name == "openai":
        return OpenAIProvider(model=settings.ai_model, api_key=settings.openai_api_key)
    raise ProviderConfigurationError(f"Unsupported AI_PROVIDER value: {settings.ai_provider}")


def _configured_provider_metadata() -> tuple[str, str]:
    provider_name = settings.ai_provider.strip().lower()
    if provider_name == "mock":
        return provider_name, MOCK_MODEL_NAME
    return provider_name, settings.ai_model


def _build_case_context(
    exception_case: ExceptionCase,
    evidence_records: list[EvidenceRecord] | None = None,
) -> dict[str, Any]:
    prompt_context = {
        "case_id": exception_case.case_id,
        "exception_type": exception_case.exception_type.value,
        "risk_level": exception_case.risk_level.value,
        "summary": exception_case.summary,
        "source_system": exception_case.source_system,
        "external_reference": exception_case.external_reference,
        "raw_context_json": exception_case.raw_context_json,
    }
    if evidence_records:
        prompt_context["evidence"] = [_build_evidence_context(record) for record in evidence_records]
    else:
        prompt_context["evidence"] = []
    return prompt_context


def _build_evidence_context(evidence_record: EvidenceRecord) -> dict[str, Any]:
    return {
        "evidence_id": evidence_record.evidence_id,
        "source_type": evidence_record.source_type.value,
        "source_name": evidence_record.source_name,
        "adapter_name": evidence_record.adapter_name,
        "status": evidence_record.status.value,
        "summary_text": evidence_record.summary_text,
        "provenance_json": evidence_record.provenance_json,
        "payload_json": evidence_record.payload_json,
        "failure_json": evidence_record.failure_json,
        "collected_at": evidence_record.collected_at.isoformat(),
    }


def _failure_result(
    *,
    provider: str,
    model: str,
    prompt_version: str,
    failure_type: str,
    message: str,
) -> AIInvocationResult:
    return AIInvocationResult(
        status=AIRecordStatus.FAILED,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        failure_json={
            "type": failure_type,
            "message": message,
        },
    )


def _to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
