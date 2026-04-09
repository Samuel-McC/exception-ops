from __future__ import annotations

from dataclasses import dataclass

from exception_ops.domain.enums import ApprovalState, RiskLevel


@dataclass(slots=True)
class ApprovalPolicyInput:
    case_risk_level: RiskLevel
    advisory_requires_approval: bool | None = None
    advisory_execution_risk: RiskLevel | None = None


@dataclass(slots=True)
class ApprovalPolicyResult:
    requires_approval: bool
    policy_reason: str
    advisory_requires_approval: bool | None
    advisory_execution_risk: RiskLevel | None


def evaluate_approval_requirement(policy_input: ApprovalPolicyInput) -> ApprovalPolicyResult:
    requires_approval = policy_input.case_risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
    if requires_approval:
        policy_reason = (
            f"Case risk level {policy_input.case_risk_level.value} requires explicit human approval."
        )
    else:
        policy_reason = (
            f"Case risk level {policy_input.case_risk_level.value} does not require approval in Phase 4."
        )

    return ApprovalPolicyResult(
        requires_approval=requires_approval,
        policy_reason=policy_reason,
        advisory_requires_approval=policy_input.advisory_requires_approval,
        advisory_execution_risk=policy_input.advisory_execution_risk,
    )


def approval_required_from_state(approval_state: ApprovalState) -> bool | None:
    if approval_state is ApprovalState.PENDING_POLICY:
        return None
    if approval_state is ApprovalState.NOT_REQUIRED:
        return False
    return True
