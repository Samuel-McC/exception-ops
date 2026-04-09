from __future__ import annotations

from pydantic import ValidationError
from temporalio import activity

from exception_ops.ai.schemas import RemediationPlanOutput
from exception_ops.db import get_session_factory
from exception_ops.db.repositories import (
    create_execution_record,
    get_exception_case,
    get_latest_ai_record,
    get_latest_execution_record,
    update_exception_case_state,
    update_execution_record,
)
from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    ExecutionRecordStatus,
    ExecutionState,
    ExceptionStatus,
    WorkflowLifecycleState,
)
from exception_ops.domain.execution_policy import (
    ExecutionDecision,
    ExecutionPolicyInput,
    evaluate_execution_policy,
)
from exception_ops.execution_adapters import (
    ExecutionAdapterConfigurationError,
    get_execution_adapter,
)

WORKFLOW_EXECUTION_ACTOR = "system:workflow"


@activity.defn
async def execute_action(case_id: str) -> dict[str, str]:
    session = get_session_factory()()
    try:
        exception_case = get_exception_case(session, case_id)
        if exception_case is None:
            raise ValueError(f"Exception case not found: {case_id}")

        latest_execution = get_latest_execution_record(session, case_id)
        if (
            latest_execution is not None
            and exception_case.execution_state in {ExecutionState.STARTED, ExecutionState.SUCCEEDED}
        ):
            return {
                "case_id": case_id,
                "execution_state": exception_case.execution_state.value,
                "workflow_lifecycle_state": exception_case.workflow_lifecycle_state.value,
                "execution_id": latest_execution.execution_id,
                "action_name": latest_execution.action_name.value,
            }

        remediation_record = get_latest_ai_record(session, case_id, AIRecordKind.REMEDIATION)
        advisory_recommended_action: str | None = None
        if remediation_record is not None and remediation_record.status is AIRecordStatus.SUCCEEDED:
            try:
                remediation_output = RemediationPlanOutput.model_validate(
                    remediation_record.payload_json or {}
                )
                advisory_recommended_action = remediation_output.recommended_action.value
            except ValidationError:
                advisory_recommended_action = None

        policy_result = evaluate_execution_policy(
            ExecutionPolicyInput(
                approval_state=exception_case.approval_state,
                advisory_recommended_action=advisory_recommended_action,
            )
        )

        if policy_result.decision is ExecutionDecision.SKIP:
            update_exception_case_state(
                session,
                case_id=case_id,
                execution_state=ExecutionState.SKIPPED,
                workflow_lifecycle_state=WorkflowLifecycleState.COMPLETED,
                status=ExceptionStatus.RESOLVED,
            )
            return {
                "case_id": case_id,
                "execution_state": ExecutionState.SKIPPED.value,
                "workflow_lifecycle_state": WorkflowLifecycleState.COMPLETED.value,
                "action_name": "",
            }

        if policy_result.decision is ExecutionDecision.BLOCK or policy_result.action_name is None:
            update_exception_case_state(
                session,
                case_id=case_id,
                execution_state=ExecutionState.PENDING,
                workflow_lifecycle_state=WorkflowLifecycleState.FAILED,
                status=ExceptionStatus.IN_REVIEW,
            )
            return {
                "case_id": case_id,
                "execution_state": ExecutionState.PENDING.value,
                "workflow_lifecycle_state": WorkflowLifecycleState.FAILED.value,
                "action_name": "",
            }

        request_payload_json = {
            "policy_reason": policy_result.policy_reason,
            "approval_state": exception_case.approval_state.value,
            "advisory_recommended_action": advisory_recommended_action,
            "source_system": exception_case.source_system,
            "external_reference": exception_case.external_reference,
        }
        execution_record = create_execution_record(
            session,
            case_id=case_id,
            action_name=policy_result.action_name,
            initiated_by=WORKFLOW_EXECUTION_ACTOR,
            status=ExecutionRecordStatus.STARTED,
            request_payload_json=request_payload_json,
        )
        update_exception_case_state(
            session,
            case_id=case_id,
            execution_state=ExecutionState.STARTED,
            workflow_lifecycle_state=WorkflowLifecycleState.STARTED,
            status=ExceptionStatus.IN_REVIEW,
        )

        try:
            adapter_result = await get_execution_adapter().execute(
                action_name=policy_result.action_name,
                exception_case=exception_case,
                request_payload_json=request_payload_json,
            )
        except ExecutionAdapterConfigurationError as exc:
            adapter_result_failure = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            update_execution_record(
                session,
                execution_id=execution_record.execution_id,
                status=ExecutionRecordStatus.FAILED,
                failure_payload_json=adapter_result_failure,
            )
            update_exception_case_state(
                session,
                case_id=case_id,
                execution_state=ExecutionState.FAILED,
                workflow_lifecycle_state=WorkflowLifecycleState.FAILED,
                status=ExceptionStatus.IN_REVIEW,
            )
            return {
                "case_id": case_id,
                "execution_state": ExecutionState.FAILED.value,
                "workflow_lifecycle_state": WorkflowLifecycleState.FAILED.value,
                "execution_id": execution_record.execution_id,
                "action_name": policy_result.action_name.value,
            }

        if adapter_result.failure_payload_json is not None:
            update_execution_record(
                session,
                execution_id=execution_record.execution_id,
                status=ExecutionRecordStatus.FAILED,
                failure_payload_json=adapter_result.failure_payload_json,
            )
            update_exception_case_state(
                session,
                case_id=case_id,
                execution_state=ExecutionState.FAILED,
                workflow_lifecycle_state=WorkflowLifecycleState.FAILED,
                status=ExceptionStatus.IN_REVIEW,
            )
            return {
                "case_id": case_id,
                "execution_state": ExecutionState.FAILED.value,
                "workflow_lifecycle_state": WorkflowLifecycleState.FAILED.value,
                "execution_id": execution_record.execution_id,
                "action_name": policy_result.action_name.value,
            }

        update_execution_record(
            session,
            execution_id=execution_record.execution_id,
            status=ExecutionRecordStatus.SUCCEEDED,
            result_payload_json=adapter_result.result_payload_json,
        )
        update_exception_case_state(
            session,
            case_id=case_id,
            execution_state=ExecutionState.SUCCEEDED,
            workflow_lifecycle_state=WorkflowLifecycleState.COMPLETED,
            status=ExceptionStatus.RESOLVED,
        )
        return {
            "case_id": case_id,
            "execution_state": ExecutionState.SUCCEEDED.value,
            "workflow_lifecycle_state": WorkflowLifecycleState.COMPLETED.value,
            "execution_id": execution_record.execution_id,
            "action_name": policy_result.action_name.value,
        }
    finally:
        session.close()
