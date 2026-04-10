from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from exception_ops.api.routes.exceptions import router as exceptions_router
from exception_ops.api.routes.health import router as health_router
from exception_ops.api.routes.operator import router as operator_router
from exception_ops.config import settings
from exception_ops.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.db_auto_create:
        logger.warning(
            "DB_AUTO_CREATE is enabled. Alembic migrations are the authoritative schema path; "
            "use automatic create_all only as a temporary dev/test fallback."
        )
        init_db()
    yield

app = FastAPI(
    title="ExceptionOps",
    version="0.1.0",
    description="AI-assisted exception-resolution platform.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(exceptions_router)
app.include_router(operator_router)
