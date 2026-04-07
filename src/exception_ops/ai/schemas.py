from __future__ import annotations

from pydantic import BaseModel, Field

from exception_ops.domain.enums import AIRecordStatus, ExceptionType, RiskLevel, WorkflowLifecycleState


class ClassificationOutput(BaseModel):
    normalized_exception_type: ExceptionType
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level_suggestion: RiskLevel
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    missing_information: list[str] = Field(default_factory=list)


class RemediationPlanOutput(BaseModel):
    recommended_action: str = Field(min_length=1, max_length=255)
    operator_summary: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=2000)
    execution_risk: RiskLevel
    requires_approval: bool
    blockers: list[str] = Field(default_factory=list)


class AIActivityResult(BaseModel):
    record_status: AIRecordStatus
    workflow_lifecycle_state: WorkflowLifecycleState
