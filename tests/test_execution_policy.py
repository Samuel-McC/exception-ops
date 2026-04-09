from __future__ import annotations

from exception_ops.domain.enums import ApprovalState, ExecutionAction
from exception_ops.domain.execution_policy import (
    ExecutionDecision,
    ExecutionPolicyInput,
    evaluate_execution_policy,
)


def test_execution_is_blocked_while_approval_is_pending() -> None:
    result = evaluate_execution_policy(
        ExecutionPolicyInput(
            approval_state=ApprovalState.PENDING,
            advisory_recommended_action=ExecutionAction.RETRY_PROVIDER_AFTER_VALIDATION.value,
        )
    )

    assert result.decision is ExecutionDecision.BLOCK
    assert result.action_name is None


def test_execution_is_skipped_for_rejected_cases() -> None:
    result = evaluate_execution_policy(
        ExecutionPolicyInput(
            approval_state=ApprovalState.REJECTED,
            advisory_recommended_action=ExecutionAction.RETRY_PROVIDER_AFTER_VALIDATION.value,
        )
    )

    assert result.decision is ExecutionDecision.SKIP
    assert result.action_name is None


def test_execution_is_allowed_for_approved_or_not_required_cases() -> None:
    approved = evaluate_execution_policy(
        ExecutionPolicyInput(
            approval_state=ApprovalState.APPROVED,
            advisory_recommended_action=ExecutionAction.RETRY_PROVIDER_AFTER_VALIDATION.value,
        )
    )
    not_required = evaluate_execution_policy(
        ExecutionPolicyInput(
            approval_state=ApprovalState.NOT_REQUIRED,
            advisory_recommended_action=ExecutionAction.REQUEST_MISSING_DOCUMENT.value,
        )
    )

    assert approved.decision is ExecutionDecision.EXECUTE
    assert approved.action_name is ExecutionAction.RETRY_PROVIDER_AFTER_VALIDATION
    assert not_required.decision is ExecutionDecision.EXECUTE
    assert not_required.action_name is ExecutionAction.REQUEST_MISSING_DOCUMENT


def test_non_allowlisted_advisory_action_falls_back_to_manual_triage() -> None:
    result = evaluate_execution_policy(
        ExecutionPolicyInput(
            approval_state=ApprovalState.APPROVED,
            advisory_recommended_action="delete_everything",
        )
    )

    assert result.decision is ExecutionDecision.EXECUTE
    assert result.action_name is ExecutionAction.MANUAL_TRIAGE
