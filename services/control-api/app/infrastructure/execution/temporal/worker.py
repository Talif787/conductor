"""Temporal worker entrypoint: python -m app.infrastructure.execution.temporal.worker

Builds the same tool invoker the API uses (builtin + http + mcp) plus a unit of
work factory, then hosts the run workflow and its activity on the configured
task queue.
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.application.execution.ports import LLMGateway
from app.application.ports import UnitOfWork
from app.config.settings import AppSettings, get_settings
from app.infrastructure.execution.http_invoker import HttpToolInvoker
from app.infrastructure.execution.mcp_invoker import McpToolInvoker
from app.infrastructure.execution.temporal.activities import ExecutionActivities
from app.infrastructure.execution.temporal.workflow import ConductorRunWorkflow
from app.infrastructure.execution.tool_invoker import BuiltinToolInvoker, CompositeToolInvoker
from app.infrastructure.http.http_client import HttpxToolClient
from app.infrastructure.llm.gateway import FakeLLMGateway, HttpLLMGateway
from app.infrastructure.mcp.mcp_client import JsonRpcMcpToolClient
from app.infrastructure.persistence.session import create_engine, create_session_factory
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

logger = logging.getLogger("conductor.worker")


def _build_invoker(settings: AppSettings) -> CompositeToolInvoker:
    llm_cfg = settings.llm
    if llm_cfg.provider == "http":
        llm: LLMGateway = HttpLLMGateway(
            base_url=llm_cfg.base_url,
            api_key=llm_cfg.api_key,
            model=llm_cfg.model,
            timeout_seconds=llm_cfg.timeout_seconds,
        )
    else:
        llm = FakeLLMGateway()
    return CompositeToolInvoker(
        builtin=BuiltinToolInvoker(llm),
        http=HttpToolInvoker(HttpxToolClient()),
        mcp=McpToolInvoker(JsonRpcMcpToolClient()),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    def uow_factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    activities = ExecutionActivities(uow_factory, _build_invoker(settings))

    client = await Client.connect(settings.temporal.host, namespace=settings.temporal.namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal.task_queue,
        workflows=[ConductorRunWorkflow],
        activities=[activities.run_tool],
    )
    logger.info(
        "worker starting host=%s namespace=%s task_queue=%s",
        settings.temporal.host,
        settings.temporal.namespace,
        settings.temporal.task_queue,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
