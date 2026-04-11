from __future__ import annotations

from dataclasses import dataclass

from exception_ops.ai.schemas import ClassificationOutput
from exception_ops.config import settings
from exception_ops.domain.enums import ExceptionType, RiskLevel
from exception_ops.domain.models import EvidenceRecord, ExceptionCase

TRIAGE_PROMPT_VERSION = "classification.v3.triage"
PLANNING_PROMPT_VERSION = "remediation.v3.plan"


@dataclass(slots=True)
class AIRoutingDecision:
    task_name: str
    path_name: str
    provider: str
    model: str
    prompt_version: str
    complexity_level: str
    routing_factors: list[str]
    escalation_requested: bool
    escalated: bool
    compatibility_mode: bool


def route_classification(
    exception_case: ExceptionCase,
    evidence_records: list[EvidenceRecord] | None = None,
) -> AIRoutingDecision:
    del exception_case, evidence_records
    provider, model, compatibility_mode = _resolve_task_target(
        provider_override=settings.ai_triage_provider,
        model_override=settings.ai_triage_model,
    )
    routing_factors = ["task_type=classification", "path=triage"]
    if compatibility_mode:
        routing_factors.append("compatibility_mode=global_ai_provider_model")

    return AIRoutingDecision(
        task_name="classification",
        path_name="triage",
        provider=provider,
        model=model,
        prompt_version=TRIAGE_PROMPT_VERSION,
        complexity_level="standard",
        routing_factors=routing_factors,
        escalation_requested=False,
        escalated=False,
        compatibility_mode=compatibility_mode,
    )


def route_remediation(
    exception_case: ExceptionCase,
    evidence_records: list[EvidenceRecord] | None = None,
    classification_output: ClassificationOutput | None = None,
) -> AIRoutingDecision:
    routing_factors = ["task_type=remediation", "path=planner_default"]
    failed_evidence_count = sum(
        1 for record in evidence_records or [] if record.status.value == "failed"
    )

    escalation_requested = False
    if exception_case.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
        routing_factors.append("risk_level_requires_stronger_reasoning")
        escalation_requested = True
    if classification_output is None:
        routing_factors.append("classification_unavailable")
        escalation_requested = True
    else:
        if classification_output.confidence < settings.ai_triage_confidence_threshold:
            routing_factors.append("triage_confidence_below_threshold")
            escalation_requested = True
        if classification_output.missing_information:
            routing_factors.append("triage_missing_information")
            escalation_requested = True
        if classification_output.normalized_exception_type is ExceptionType.UNKNOWN:
            routing_factors.append("normalized_exception_type_unknown")
            escalation_requested = True
    if exception_case.exception_type is ExceptionType.UNKNOWN:
        routing_factors.append("source_exception_type_unknown")
        escalation_requested = True
    if failed_evidence_count > 0:
        routing_factors.append("evidence_collection_incomplete")
        escalation_requested = True
    if len(exception_case.summary) > 160:
        routing_factors.append("summary_length_complex")
        escalation_requested = True

    provider_override = settings.ai_planner_provider
    model_override = settings.ai_planner_model
    compatibility_mode = not (provider_override.strip() or model_override.strip())
    path_name = "planner_default"
    escalated = False

    if escalation_requested and _planner_escalation_configured():
        provider_override = settings.ai_planner_escalation_provider
        model_override = settings.ai_planner_escalation_model
        compatibility_mode = False
        path_name = "planner_escalated"
        escalated = True
        routing_factors.append("planner_escalation_configured")
    elif escalation_requested:
        routing_factors.append("planner_escalation_not_configured")

    provider, model, resolved_compatibility_mode = _resolve_task_target(
        provider_override=provider_override,
        model_override=model_override,
    )
    compatibility_mode = compatibility_mode or resolved_compatibility_mode
    if compatibility_mode:
        routing_factors.append("compatibility_mode=global_ai_provider_model")

    return AIRoutingDecision(
        task_name="remediation",
        path_name=path_name,
        provider=provider,
        model=model,
        prompt_version=PLANNING_PROMPT_VERSION,
        complexity_level="complex" if escalation_requested else "standard",
        routing_factors=routing_factors,
        escalation_requested=escalation_requested,
        escalated=escalated,
        compatibility_mode=compatibility_mode,
    )


def get_fallback_target() -> tuple[str, str] | None:
    provider = settings.ai_fallback_provider.strip().lower()
    model = settings.ai_fallback_model.strip()
    if not provider:
        return None
    if not model:
        model = settings.ai_model
    return provider, model


def _resolve_task_target(
    *,
    provider_override: str,
    model_override: str,
) -> tuple[str, str, bool]:
    compatibility_mode = not (provider_override.strip() or model_override.strip())
    provider = provider_override.strip().lower() or settings.ai_provider.strip().lower()
    model = model_override.strip() or settings.ai_model
    return provider, model, compatibility_mode


def _planner_escalation_configured() -> bool:
    return bool(
        settings.ai_planner_escalation_provider.strip()
        or settings.ai_planner_escalation_model.strip()
    )
