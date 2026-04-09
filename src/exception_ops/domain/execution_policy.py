from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from exception_ops.domain.enums import ApprovalState, ExecutionAction


class ExecutionDecision(StrEnum):
    EXECUTE = "execute"
    SKIP = "skip"
    BLOCK = "block"


@dataclass(slots=True)
class ExecutionPolicyInput:
    approval_state: ApprovalState
    advisory_recommended_action: str | None = None


@dataclass(slots=True)
class ExecutionPolicyResult:
    decision: ExecutionDecision
    action_name: ExecutionAction | None
    policy_reason: str


def evaluate_execution_policy(policy_input: ExecutionPolicyInput) -> ExecutionPolicyResult:
    if policy_input.approval_state is ApprovalState.REJECTED:
        return ExecutionPolicyResult(
            decision=ExecutionDecision.SKIP,
            action_name=None,
            policy_reason="Rejected cases terminate without execution.",
        )

    if policy_input.approval_state not in {ApprovalState.APPROVED, ApprovalState.NOT_REQUIRED}:
        return ExecutionPolicyResult(
            decision=ExecutionDecision.BLOCK,
            action_name=None,
            policy_reason=(
                f"Execution is blocked while approval_state={policy_input.approval_state.value}."
            ),
        )

    if policy_input.advisory_recommended_action is not None:
        try:
            action_name = ExecutionAction(policy_input.advisory_recommended_action)
        except ValueError:
            action_name = ExecutionAction.MANUAL_TRIAGE
            return ExecutionPolicyResult(
                decision=ExecutionDecision.EXECUTE,
                action_name=action_name,
                policy_reason=(
                    "Advisory remediation action was not allowlisted, so execution fell back to "
                    "manual_triage."
                ),
            )
    else:
        action_name = ExecutionAction.MANUAL_TRIAGE

    return ExecutionPolicyResult(
        decision=ExecutionDecision.EXECUTE,
        action_name=action_name,
        policy_reason=(
            f"Execution is permitted for approval_state={policy_input.approval_state.value}."
        ),
    )
