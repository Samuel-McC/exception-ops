from __future__ import annotations

from exception_ops.domain.approval_policy import (
    ApprovalPolicyInput,
    approval_required_from_state,
    evaluate_approval_requirement,
)
from exception_ops.domain.enums import ApprovalState, RiskLevel


def test_medium_and_high_risk_cases_require_approval() -> None:
    medium = evaluate_approval_requirement(ApprovalPolicyInput(case_risk_level=RiskLevel.MEDIUM))
    high = evaluate_approval_requirement(ApprovalPolicyInput(case_risk_level=RiskLevel.HIGH))

    assert medium.requires_approval is True
    assert high.requires_approval is True


def test_ai_advice_does_not_auto_approve_low_risk_cases() -> None:
    result = evaluate_approval_requirement(
        ApprovalPolicyInput(
            case_risk_level=RiskLevel.LOW,
            advisory_requires_approval=True,
            advisory_execution_risk=RiskLevel.HIGH,
        )
    )

    assert result.requires_approval is False
    assert result.advisory_requires_approval is True
    assert result.advisory_execution_risk is RiskLevel.HIGH


def test_approval_required_from_state_is_explicit() -> None:
    assert approval_required_from_state(ApprovalState.PENDING_POLICY) is None
    assert approval_required_from_state(ApprovalState.NOT_REQUIRED) is False
    assert approval_required_from_state(ApprovalState.PENDING) is True
    assert approval_required_from_state(ApprovalState.APPROVED) is True
    assert approval_required_from_state(ApprovalState.REJECTED) is True
