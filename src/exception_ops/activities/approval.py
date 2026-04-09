from __future__ import annotations

from pydantic import ValidationError
from temporalio import activity

from exception_ops.ai.schemas import RemediationPlanOutput
from exception_ops.db import get_session_factory
from exception_ops.db.repositories import (
    apply_approval_decision,
    get_exception_case,
    get_latest_ai_record,
    update_exception_case_state,
)
from exception_ops.domain.approval_policy import ApprovalPolicyInput, evaluate_approval_requirement
from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    ApprovalState,
    ExecutionState,
    ExceptionStatus,
    RiskLevel,
    WorkflowLifecycleState,
)


@activity.defn
async def evaluate_approval_gate(case_id: str) -> dict[str, str | bool]:
    session = get_session_factory()()
    try:
        exception_case = get_exception_case(session, case_id)
        if exception_case is None:
            raise ValueError(f"Exception case not found: {case_id}")

        remediation_record = get_latest_ai_record(session, case_id, AIRecordKind.REMEDIATION)
        advisory_requires_approval = None
        advisory_execution_risk: RiskLevel | None = None
        if remediation_record is not None and remediation_record.status is AIRecordStatus.SUCCEEDED:
            try:
                remediation_output = RemediationPlanOutput.model_validate(
                    remediation_record.payload_json or {}
                )
                advisory_requires_approval = remediation_output.requires_approval
                advisory_execution_risk = remediation_output.execution_risk
            except ValidationError:
                advisory_requires_approval = None
                advisory_execution_risk = None

        policy_result = evaluate_approval_requirement(
            ApprovalPolicyInput(
                case_risk_level=exception_case.risk_level,
                advisory_requires_approval=advisory_requires_approval,
                advisory_execution_risk=advisory_execution_risk,
            )
        )
        approval_state = (
            ApprovalState.PENDING if policy_result.requires_approval else ApprovalState.NOT_REQUIRED
        )
        workflow_state = WorkflowLifecycleState.STARTED
        update_exception_case_state(
            session,
            case_id=case_id,
            approval_state=approval_state,
            execution_state=ExecutionState.PENDING,
            status=ExceptionStatus.IN_REVIEW,
            workflow_lifecycle_state=workflow_state,
        )
        return {
            "case_id": case_id,
            "requires_approval": policy_result.requires_approval,
            "approval_state": approval_state.value,
            "policy_reason": policy_result.policy_reason,
            "workflow_lifecycle_state": workflow_state.value,
        }
    finally:
        session.close()


@activity.defn
async def finalize_approval_decision(decision_id: str) -> dict[str, str]:
    session = get_session_factory()()
    try:
        exception_case, decision = apply_approval_decision(
            session,
            decision_id=decision_id,
        )
        return {
            "case_id": exception_case.case_id,
            "decision_id": decision.decision_id,
            "approval_state": exception_case.approval_state.value,
            "workflow_lifecycle_state": exception_case.workflow_lifecycle_state.value,
        }
    finally:
        session.close()
