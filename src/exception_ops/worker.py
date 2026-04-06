from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from exception_ops.activities.classification import classify_exception
from exception_ops.activities.evidence import collect_evidence
from exception_ops.activities.execution import execute_action
from exception_ops.activities.remediation import generate_remediation_plan
from exception_ops.config import settings
from exception_ops.workflows.exception_resolution import ExceptionResolutionWorkflow


async def main() -> None:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ExceptionResolutionWorkflow],
        activities=[
            classify_exception,
            collect_evidence,
            generate_remediation_plan,
            execute_action,
        ],
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
