from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from exception_ops.ai.providers import (
    AIProvider,
    MockAIProvider,
    OpenAIProvider,
    ProviderConfigurationError,
    ProviderUsage,
)
from exception_ops.ai.routing import (
    AIRoutingDecision,
    get_fallback_target,
    route_classification,
    route_remediation,
)
from exception_ops.ai.schemas import (
    AIRouteAttempt,
    AIRouteMetadata,
    AIStageTraceMetadata,
    AIUsageMetadata,
    ClassificationOutput,
    RemediationPlanOutput,
)
from exception_ops.config import settings
from exception_ops.domain.enums import AIRecordStatus
from exception_ops.domain.models import EvidenceRecord, ExceptionCase


@dataclass(slots=True)
class AIInvocationResult:
    status: AIRecordStatus
    provider: str
    model: str
    prompt_version: str
    payload_json: dict[str, Any] | None = None
    failure_json: dict[str, Any] | None = None
    route_json: dict[str, Any] | None = None
    usage_json: dict[str, Any] | None = None
    trace_json: dict[str, Any] | None = None


class ExceptionAIService:
    async def classify_exception(
        self,
        exception_case: ExceptionCase,
        evidence_records: list[EvidenceRecord] | None = None,
    ) -> AIInvocationResult:
        routing_decision = route_classification(exception_case, evidence_records)
        prompt_context = _build_case_context(exception_case, evidence_records)
        system_prompt = (
            "You are ExceptionOps triage classification. Use the provided source case data as source truth and "
            "treat collected evidence as bounded supporting context only. Return a structured classification that "
            "matches the schema exactly. Do not recommend approval or execution."
        )
        user_prompt = (
            "Classify this exception into the bounded taxonomy and suggest a risk level using the source case "
            "data plus any collected evidence.\n\n"
            f"Prompt version: {routing_decision.prompt_version}\n"
            f"Case context:\n{_to_json(prompt_context)}"
        )

        return await self._generate(
            routing_decision=routing_decision,
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
        routing_decision = route_remediation(
            exception_case,
            evidence_records,
            classification_output,
        )
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
            f"Prompt version: {routing_decision.prompt_version}\n"
            f"Case context:\n{_to_json(prompt_context)}"
        )

        return await self._generate(
            routing_decision=routing_decision,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_context=prompt_context,
            response_model=RemediationPlanOutput,
        )

    async def _generate(
        self,
        *,
        routing_decision: AIRoutingDecision,
        system_prompt: str,
        user_prompt: str,
        prompt_context: dict[str, Any],
        response_model: type[BaseModel],
    ) -> AIInvocationResult:
        attempts: list[AIRouteAttempt] = []
        if not settings.ai_enabled:
            return _failure_result(
                provider=routing_decision.provider,
                model=routing_decision.model,
                prompt_version=routing_decision.prompt_version,
                routing_decision=routing_decision,
                attempts=attempts,
                failure_type="ai_disabled",
                message="AI generation is disabled by configuration.",
            )

        try:
            primary_provider = _build_ai_provider(
                routing_decision.provider,
                routing_decision.model,
            )
            primary_result = await primary_provider.generate_structured(
                task_name=routing_decision.task_name,
                prompt_version=routing_decision.prompt_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_context=prompt_context,
                response_model=response_model,
            )
        except (OpenAIError, ProviderConfigurationError, RuntimeError, ValidationError, ValueError) as exc:
            attempts.append(
                AIRouteAttempt(
                    provider=routing_decision.provider,
                    model=routing_decision.model,
                    outcome="failed",
                    failure_type=type(exc).__name__,
                    failure_message=str(exc),
                )
            )
            return await self._retry_with_fallback_or_fail(
                routing_decision=routing_decision,
                attempts=attempts,
                primary_failure=exc,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_context=prompt_context,
                response_model=response_model,
            )

        attempts.append(
            AIRouteAttempt(
                provider=primary_provider.metadata.provider,
                model=primary_provider.metadata.model,
                outcome="succeeded",
            )
        )
        return _success_result(
            provider=primary_provider.metadata.provider,
            model=primary_provider.metadata.model,
            prompt_version=routing_decision.prompt_version,
            payload_json=primary_result.output.model_dump(mode="json"),
            routing_decision=routing_decision,
            attempts=attempts,
            usage=primary_result.usage,
            fallback_occurred=False,
        )

    async def _retry_with_fallback_or_fail(
        self,
        *,
        routing_decision: AIRoutingDecision,
        attempts: list[AIRouteAttempt],
        primary_failure: Exception,
        system_prompt: str,
        user_prompt: str,
        prompt_context: dict[str, Any],
        response_model: type[BaseModel],
    ) -> AIInvocationResult:
        fallback_target = get_fallback_target()
        if (
            fallback_target is None
            or fallback_target == (routing_decision.provider, routing_decision.model)
        ):
            return _failure_result(
                provider=routing_decision.provider,
                model=routing_decision.model,
                prompt_version=routing_decision.prompt_version,
                routing_decision=routing_decision,
                attempts=attempts,
                failure_type=type(primary_failure).__name__,
                message=str(primary_failure),
            )

        fallback_provider_name, fallback_model_name = fallback_target
        try:
            fallback_provider = _build_ai_provider(
                fallback_provider_name,
                fallback_model_name,
            )
            fallback_result = await fallback_provider.generate_structured(
                task_name=routing_decision.task_name,
                prompt_version=routing_decision.prompt_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_context=prompt_context,
                response_model=response_model,
            )
        except (OpenAIError, ProviderConfigurationError, RuntimeError, ValidationError, ValueError) as exc:
            attempts.append(
                AIRouteAttempt(
                    provider=fallback_provider_name,
                    model=fallback_model_name,
                    outcome="failed",
                    failure_type=type(exc).__name__,
                    failure_message=str(exc),
                )
            )
            return _failure_result(
                provider=fallback_provider_name,
                model=fallback_model_name,
                prompt_version=routing_decision.prompt_version,
                routing_decision=routing_decision,
                attempts=attempts,
                failure_type=type(exc).__name__,
                message=str(exc),
                primary_failure_type=type(primary_failure).__name__,
                primary_failure_message=str(primary_failure),
            )

        attempts.append(
            AIRouteAttempt(
                provider=fallback_provider.metadata.provider,
                model=fallback_provider.metadata.model,
                outcome="succeeded",
            )
        )
        return _success_result(
            provider=fallback_provider.metadata.provider,
            model=fallback_provider.metadata.model,
            prompt_version=routing_decision.prompt_version,
            payload_json=fallback_result.output.model_dump(mode="json"),
            routing_decision=routing_decision,
            attempts=attempts,
            usage=fallback_result.usage,
            fallback_occurred=True,
        )


def get_ai_service() -> ExceptionAIService:
    return ExceptionAIService()


def _build_ai_provider(provider_name: str, model_name: str) -> AIProvider:
    normalized_provider_name = provider_name.strip().lower()
    if normalized_provider_name == "mock":
        return MockAIProvider(model=model_name)
    if normalized_provider_name == "openai":
        return OpenAIProvider(model=model_name, api_key=settings.openai_api_key)
    raise ProviderConfigurationError(f"Unsupported AI provider value: {provider_name}")


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


def _success_result(
    *,
    provider: str,
    model: str,
    prompt_version: str,
    payload_json: dict[str, Any],
    routing_decision: AIRoutingDecision,
    attempts: list[AIRouteAttempt],
    usage: ProviderUsage | None,
    fallback_occurred: bool,
) -> AIInvocationResult:
    route_metadata = AIRouteMetadata(
        task_name=routing_decision.task_name,  # type: ignore[arg-type]
        path_name=routing_decision.path_name,
        selected_provider=routing_decision.provider,
        selected_model=routing_decision.model,
        final_provider=provider,
        final_model=model,
        selected_prompt_version=prompt_version,
        complexity_level=routing_decision.complexity_level,  # type: ignore[arg-type]
        routing_factors=routing_decision.routing_factors,
        escalation_requested=routing_decision.escalation_requested,
        escalated=routing_decision.escalated,
        fallback_occurred=fallback_occurred,
        compatibility_mode=routing_decision.compatibility_mode,
        attempts=attempts,
    )
    trace_metadata = AIStageTraceMetadata(
        model_path=routing_decision.path_name,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        escalation_occurred=routing_decision.escalated,
        fallback_occurred=fallback_occurred,
        main_factors=routing_decision.routing_factors,
        summary=_build_trace_summary(
            task_name=routing_decision.task_name,
            path_name=routing_decision.path_name,
            provider=provider,
            model=model,
            routing_factors=routing_decision.routing_factors,
            escalated=routing_decision.escalated,
            fallback_occurred=fallback_occurred,
        ),
    )
    usage_metadata = _build_usage_metadata(usage)
    return AIInvocationResult(
        status=AIRecordStatus.SUCCEEDED,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        payload_json=payload_json,
        route_json=route_metadata.model_dump(mode="json"),
        usage_json=usage_metadata.model_dump(mode="json") if usage_metadata else None,
        trace_json=trace_metadata.model_dump(mode="json"),
    )


def _failure_result(
    *,
    provider: str,
    model: str,
    prompt_version: str,
    routing_decision: AIRoutingDecision,
    attempts: list[AIRouteAttempt],
    failure_type: str,
    message: str,
    primary_failure_type: str | None = None,
    primary_failure_message: str | None = None,
) -> AIInvocationResult:
    fallback_occurred = len(attempts) > 1
    route_metadata = AIRouteMetadata(
        task_name=routing_decision.task_name,  # type: ignore[arg-type]
        path_name=routing_decision.path_name,
        selected_provider=routing_decision.provider,
        selected_model=routing_decision.model,
        final_provider=provider,
        final_model=model,
        selected_prompt_version=prompt_version,
        complexity_level=routing_decision.complexity_level,  # type: ignore[arg-type]
        routing_factors=routing_decision.routing_factors,
        escalation_requested=routing_decision.escalation_requested,
        escalated=routing_decision.escalated,
        fallback_occurred=fallback_occurred,
        compatibility_mode=routing_decision.compatibility_mode,
        attempts=attempts,
    )
    trace_metadata = AIStageTraceMetadata(
        model_path=routing_decision.path_name,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        escalation_occurred=routing_decision.escalated,
        fallback_occurred=fallback_occurred,
        main_factors=routing_decision.routing_factors,
        summary=_build_trace_summary(
            task_name=routing_decision.task_name,
            path_name=routing_decision.path_name,
            provider=provider,
            model=model,
            routing_factors=routing_decision.routing_factors,
            escalated=routing_decision.escalated,
            fallback_occurred=fallback_occurred,
        ),
    )
    failure_json: dict[str, Any] = {
        "type": failure_type,
        "message": message,
    }
    if primary_failure_type is not None:
        failure_json["primary_failure_type"] = primary_failure_type
    if primary_failure_message is not None:
        failure_json["primary_failure_message"] = primary_failure_message

    return AIInvocationResult(
        status=AIRecordStatus.FAILED,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        failure_json=failure_json,
        route_json=route_metadata.model_dump(mode="json"),
        trace_json=trace_metadata.model_dump(mode="json"),
    )


def _build_usage_metadata(usage: ProviderUsage | None) -> AIUsageMetadata | None:
    if usage is None:
        return None
    return AIUsageMetadata(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=usage.estimated_cost_usd,
        is_estimated=usage.is_estimated,
    )


def _build_trace_summary(
    *,
    task_name: str,
    path_name: str,
    provider: str,
    model: str,
    routing_factors: list[str],
    escalated: bool,
    fallback_occurred: bool,
) -> str:
    factor_summary = ", ".join(routing_factors[:3]) if routing_factors else "default bounded routing"
    status_parts = []
    if escalated:
        status_parts.append("escalated")
    if fallback_occurred:
        status_parts.append("fallback")
    status_label = f" ({', '.join(status_parts)})" if status_parts else ""
    stage_label = "triage" if task_name == "classification" else "planning"
    return (
        f"{stage_label.title()} used {path_name}{status_label} via {provider}/{model}; "
        f"main factors: {factor_summary}."
    )


def _to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
