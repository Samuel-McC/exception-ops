from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from exception_ops.domain.enums import (
    AIRecordStatus,
    ExecutionAction,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)


class ClassificationOutput(BaseModel):
    normalized_exception_type: ExceptionType
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level_suggestion: RiskLevel
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    missing_information: list[str] = Field(default_factory=list)


class RemediationPlanOutput(BaseModel):
    recommended_action: ExecutionAction
    operator_summary: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=2000)
    execution_risk: RiskLevel
    requires_approval: bool
    blockers: list[str] = Field(default_factory=list)


class AIRouteAttempt(BaseModel):
    provider: str
    model: str
    outcome: Literal["succeeded", "failed"]
    failure_type: str | None = None
    failure_message: str | None = None


class AIRouteMetadata(BaseModel):
    task_name: Literal["classification", "remediation"]
    path_name: str
    selected_provider: str
    selected_model: str
    final_provider: str
    final_model: str
    selected_prompt_version: str
    complexity_level: Literal["standard", "complex"]
    routing_factors: list[str] = Field(default_factory=list)
    escalation_requested: bool = False
    escalated: bool = False
    fallback_occurred: bool = False
    compatibility_mode: bool = False
    attempts: list[AIRouteAttempt] = Field(default_factory=list)


class AIUsageMetadata(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    is_estimated: bool = False


class AIStageTraceMetadata(BaseModel):
    model_path: str
    provider: str
    model: str
    prompt_version: str
    escalation_occurred: bool = False
    fallback_occurred: bool = False
    main_factors: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=1000)


class AIActivityResult(BaseModel):
    record_status: AIRecordStatus
    workflow_lifecycle_state: WorkflowLifecycleState
