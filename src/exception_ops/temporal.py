from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from temporalio.client import Client
from temporalio.service import RPCError

from exception_ops.config import settings
from exception_ops.workflows.exception_resolution import ExceptionResolutionWorkflow

WORKFLOW_ID_PREFIX = "exception-resolution"


def build_exception_workflow_id(case_id: str) -> str:
    return f"{WORKFLOW_ID_PREFIX}-{case_id}"


@dataclass(slots=True)
class WorkflowStartResult:
    workflow_id: str
    run_id: str | None


class WorkflowStarter(Protocol):
    async def start_exception_workflow(self, case_id: str, workflow_id: str) -> WorkflowStartResult:
        ...


class WorkflowSignaler(Protocol):
    async def signal_approval_decision(self, workflow_id: str, decision_id: str) -> None:
        ...


class WorkflowStartError(Exception):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"Unable to start workflow {workflow_id}")
        self.workflow_id = workflow_id


class WorkflowSignalError(Exception):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"Unable to signal workflow {workflow_id}")
        self.workflow_id = workflow_id


class TemporalWorkflowStarter:
    async def start_exception_workflow(self, case_id: str, workflow_id: str) -> WorkflowStartResult:
        try:
            client = await Client.connect(
                settings.temporal_host,
                namespace=settings.temporal_namespace,
            )
            handle = await client.start_workflow(
                ExceptionResolutionWorkflow.run,
                case_id,
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
            )
        except (OSError, RPCError) as exc:
            raise WorkflowStartError(workflow_id) from exc

        return WorkflowStartResult(
            workflow_id=handle.id,
            run_id=handle.result_run_id or handle.first_execution_run_id,
        )


class TemporalWorkflowSignaler:
    async def signal_approval_decision(self, workflow_id: str, decision_id: str) -> None:
        try:
            client = await Client.connect(
                settings.temporal_host,
                namespace=settings.temporal_namespace,
            )
            handle = client.get_workflow_handle(workflow_id)
            await handle.signal(
                ExceptionResolutionWorkflow.submit_approval_decision,
                decision_id,
            )
        except (OSError, RPCError) as exc:
            raise WorkflowSignalError(workflow_id) from exc


def get_workflow_starter() -> WorkflowStarter:
    return TemporalWorkflowStarter()


def get_workflow_signaler() -> WorkflowSignaler:
    return TemporalWorkflowSignaler()
